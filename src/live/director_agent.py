"""DirectorAgent — proactive LLM loop that drives continuous TTS output.

The director fires whenever the TTS queue is idle, or at most every
MAX_SILENCE_SECONDS seconds. It collects full context (script state,
product knowledge, recent events) and asks Gemini to produce the next
utterance, optionally improving on the script text.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time

from src.live.schema import DirectorOutput, Event

logger = logging.getLogger(__name__)

MAX_SILENCE_SECONDS = 15.0   # force a generation if TTS has been idle this long (safety net)
TARGET_QUEUE_DEPTH = 10      # keep this many sentences pre-generated as pending text
MAX_CONCURRENT_LLM = 2       # max parallel LLM calls (avoids flooding, keeps context fresh)

_SYSTEM_PROMPT = """\
你是一个经验丰富的带货主播，正在进行抖音直播。
你的任务是：根据当前直播脚本段落、产品知识和观众互动，决定下一句要说什么。

规则：
- 优先回应观众互动（问题、礼物、热情弹幕），但不能忽视脚本进度
- 改写脚本内容，让它听起来更自然、口语化，而不是照本宣科
- 如果脚本段落标记了 must_say=true，必须基于脚本原文，不可大幅偏离
- 每次只说一句话，不超过 30 字
- 禁用词不得出现在输出中
- speech_prompt 描述朗读时的情绪、语速和语气（一句话，要具体）

返回严格的 JSON，格式：
{
  "content": "下一句台词（不超过30字）",
  "speech_prompt": "朗读风格描述",
  "source": "script" | "interaction" | "knowledge",
  "reason": "决策理由（简短）"
}
不要输出 JSON 以外的任何内容。
"""


def build_director_prompt(
    script_state: dict,
    knowledge_ctx: str,
    recent_events: list[Event],
    last_said: str,
    persona_ctx: str = "",
) -> str:
    """Build the user-turn prompt for the director LLM call."""
    event_lines = "\n".join(
        f"  - [{e.type}] {e.user}: {e.text or e.gift or '(进场)'}"
        for e in recent_events[-10:]
    ) or "  （暂无互动）"

    persona_section = f"=== 主播人设 ===\n{persona_ctx}\n\n" if persona_ctx else ""

    must_say = script_state.get("must_say", False)
    cue = script_state.get("cue") or []
    if cue:
        cue_label = "以下话术必须全部逐字说出" if must_say else "请在合适时机自然融入，尽量覆盖"
        cue_lines = "\n".join(f"  - {line}" for line in cue)
        cue_section = f"锚点话术（{cue_label}）：\n{cue_lines}\n"
    else:
        cue_section = ""

    return (
        f"{persona_section}"
        f"=== 产品知识 ===\n{knowledge_ctx}\n\n"
        f"=== 当前脚本段落 ===\n"
        f"阶段：{script_state.get('title', '')}\n"
        f"目标：{script_state.get('goal', '').strip()}\n"
        f"{cue_section}"
        f"关键词：{', '.join(script_state.get('keywords') or [])}\n"
        f"剩余时间：{script_state.get('remaining_seconds', 0):.0f}s\n\n"
        f"=== 最近观众互动 ===\n{event_lines}\n\n"
        f"=== 上一句说的 ===\n{last_said or '（开场，还没说过话）'}\n\n"
        f"请决定下一句说什么。"
    )


def parse_director_response(raw: str) -> DirectorOutput:
    """Parse LLM JSON output into a DirectorOutput. Returns a fallback on error."""
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        data = json.loads(text)
        return DirectorOutput(
            content=data.get("content", ""),
            speech_prompt=data.get("speech_prompt", "自然平稳地说"),
            source=data.get("source", "script"),
            reason=data.get("reason", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Director parse error: %s | raw=%s", e, raw[:200])
        return DirectorOutput(content="", speech_prompt="", source="script", reason=f"parse error: {e}")


class DirectorAgent:
    """Proactive TTS driver. Fires whenever TTS is idle or silence exceeds threshold.

    Args:
        tts_queue: Queue of (text, speech_prompt) tuples consumed by TTSPlayer.
        tts_player: TTSPlayer instance; used to check `is_speaking`.
        knowledge_ctx: Pre-formatted product knowledge string for LLM prompt.
        llm_generate_fn: Callable(prompt: str) -> str. Returns raw LLM JSON text.
        persona_ctx: Optional persona information (e.g., streamer name, style, forbidden words).
    """

    def __init__(
        self,
        tts_queue: queue.Queue,
        tts_player: object,
        knowledge_ctx: str,
        llm_generate_fn,
        urgent_queue: queue.Queue | None = None,
        persona_ctx: str = "",
    ) -> None:
        self._tts_queue = tts_queue
        self._tts_player = tts_player
        self._knowledge_ctx = knowledge_ctx
        self._persona_ctx = persona_ctx
        self._llm_generate = llm_generate_fn
        self._urgent_queue = urgent_queue
        self._last_said = ""
        self._last_silence_check = 0.0
        self._llm_semaphore = threading.Semaphore(MAX_CONCURRENT_LLM)
        self._llm_in_flight_count = 0  # number of LLM calls currently running
        self._count_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, get_state_fn, get_events_fn) -> None:
        """Start the director background thread.

        Args:
            get_state_fn: Callable() -> dict (current script state snapshot).
            get_events_fn: Callable() -> list[Event] (recent buffered events).
        """
        self._thread = threading.Thread(
            target=self._run,
            args=(get_state_fn, get_events_fn),
            daemon=True,
            name="DirectorAgent",
        )
        self._thread.start()
        logger.info("DirectorAgent started")

    @property
    def is_generating(self) -> bool:
        with self._count_lock:
            return self._llm_in_flight_count > 0

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self, get_state_fn, get_events_fn) -> None:
        last_fire_time = 0.0
        while not self._stop_event.is_set():
            state = get_state_fn()
            if state.get("finished"):
                break

            now = time.monotonic()
            queue_depth = self._tts_queue.qsize()
            with self._count_lock:
                in_flight = self._llm_in_flight_count
            # Count in-flight LLM calls as "pending sentences" to avoid over-scheduling.
            # Without this, concurrent LLM calls all see qsize < TARGET and keep firing.
            effective_depth = queue_depth + in_flight
            queue_needs_fill = effective_depth < TARGET_QUEUE_DEPTH
            # Safety net: if nothing has been fired for MAX_SILENCE_SECONDS and queue is empty,
            # force a generation regardless of in-flight count.
            # Track last_fire_time (updated every fire) so the timer resets correctly.
            silence_too_long = (now - last_fire_time) >= MAX_SILENCE_SECONDS and effective_depth == 0

            # Fire async: keep effective queue depth at TARGET_QUEUE_DEPTH.
            # Allow up to MAX_CONCURRENT_LLM parallel calls; semaphore blocks if saturated.
            can_acquire = self._llm_semaphore.acquire(blocking=False)
            if can_acquire and (queue_needs_fill or silence_too_long):
                last_fire_time = now
                events = get_events_fn()
                t = threading.Thread(
                    target=self._fire, args=(state, events), daemon=True, name="DirectorFire"
                )
                t.start()
            elif can_acquire:
                # acquired but no work needed — release immediately
                self._llm_semaphore.release()

            self._stop_event.wait(timeout=0.5)

    def _fire(self, script_state: dict, recent_events: list[Event]) -> None:
        """Call LLM in a background thread and enqueue next utterance.

        Runs concurrently with TTS playback so the next line is ready the moment
        the current one finishes — eliminating the inter-sentence gap.
        """
        with self._count_lock:
            self._llm_in_flight_count += 1

        # Drain urgent P0/P1 events (intelligent mode)
        urgent_events: list[Event] = []
        if self._urgent_queue is not None:
            while True:
                try:
                    urgent_events.append(self._urgent_queue.get_nowait())
                except queue.Empty:
                    break

        all_events = urgent_events + recent_events

        try:
            prompt = build_director_prompt(
                script_state, self._knowledge_ctx, all_events, self._last_said, self._persona_ctx
            )
            raw = self._llm_generate(prompt)
            output = parse_director_response(raw)
        except Exception as e:
            logger.error("Director LLM call failed: %s", e)
            return
        finally:
            with self._count_lock:
                self._llm_in_flight_count -= 1
            self._llm_semaphore.release()

        if not output.content:
            return

        self._tts_player.put(output.content, output.speech_prompt, urgent=bool(urgent_events))
        self._last_said = output.content
        logger.info("[DIRECTOR] %s (%s): %s", output.source, output.reason, output.content[:60])
