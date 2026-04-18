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
from src.live.session_memory import SessionMemory

logger = logging.getLogger(__name__)

MAX_SILENCE_SECONDS = 15.0   # force a generation if TTS has been idle this long (safety net)
TARGET_QUEUE_DEPTH = 10      # keep this many sentences pre-generated as pending text
MAX_CONCURRENT_LLM = 2       # max parallel LLM calls (avoids flooding, keeps context fresh)

_SYSTEM_PROMPT = """\
你是一个经验丰富的带货主播，正在进行抖音直播。
你的任务是：根据当前直播脚本段落、产品知识、观众互动和历史记忆，决定下一句要说什么。

规则：
- 优先回应观众互动（问题、礼物、热情弹幕），但不能忽视脚本进度
- 改写脚本内容，让它听起来更自然、口语化，而不是照本宣科
- 如果脚本段落标记了 must_say=true，必须基于脚本原文，不可大幅偏离
- 每次只说一句话，不超过 30 字
- 禁用词不得出现在输出中
- speech_prompt 描述朗读时的情绪、语速和语气（一句话，要具体）

记忆使用规则（非常重要）：
- 优先讲未覆盖的锚点话术（cue 列表中标记 ✗ 的）
- 避免 5 分钟内重复同一 topic_tag
- 如果"最近问答"里有相似问题，不要重复回答，可引申到下一卖点
- topic_tag 用"类别:具体内容"格式，例如 "成分:益生菌"、"FAQ:怎么吃"、"价格优势"
- cue_hits 列出本句实际覆盖的锚点话术原文（必须是 cue 列表里的字符串）
- is_qa_answer=true 时填入 answered_question（原始问题文本）

返回严格的 JSON，格式：
{
  "content": "下一句台词（不超过30字）",
  "speech_prompt": "朗读风格描述",
  "source": "script" | "interaction" | "knowledge",
  "reason": "决策理由（简短）",
  "topic_tag": "成分:益生菌",
  "cue_hits": ["新西兰原装"],
  "is_qa_answer": false,
  "answered_question": null
}
不要输出 JSON 以外的任何内容。
"""


def build_director_prompt(
    script_state: dict,
    knowledge_ctx: str,
    recent_events: list[Event],
    memory: SessionMemory | None = None,
    persona_ctx: str = "",
) -> str:
    """Build the user-turn prompt for the director LLM call.

    Args:
        script_state: current ScriptRunner snapshot (title/goal/cue/...).
        knowledge_ctx: pre-rendered product knowledge block.
        recent_events: buffered P2/P3 events (last 10 rendered).
        memory: optional SessionMemory; when provided, renders four extra
            sections (recent utterances, topic summary, cue status, recent QA).
        persona_ctx: optional persona description.
    """
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

    memory_section = ""
    if memory is not None:
        segment_id = script_state.get("segment_id") or ""
        cue_status = memory.render_cue_status(segment_id, cue) if cue else ""
        memory_section = (
            f"=== 最近说过（防复读） ===\n{memory.render_recent()}\n\n"
            f"=== 全场已讲话题（避免重复） ===\n{memory.render_topic_summary()}\n\n"
        )
        if cue_status:
            memory_section += (
                f"=== 当前段落锚点覆盖情况 ===\n{cue_status}\n\n"
            )
        memory_section += (
            f"=== 最近问答（避免重复回答） ===\n{memory.render_recent_qa()}\n\n"
        )

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
        f"{memory_section}"
        f"请决定下一句说什么。"
    )


def parse_director_response(raw: str) -> DirectorOutput:
    """Parse LLM JSON output into a DirectorOutput. Returns a fallback on error."""
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        data = json.loads(text)
        cue_hits = data.get("cue_hits") or []
        if not isinstance(cue_hits, list):
            cue_hits = []
        return DirectorOutput(
            content=data.get("content", ""),
            speech_prompt=data.get("speech_prompt", "自然平稳地说"),
            source=data.get("source", "script"),
            reason=data.get("reason", ""),
            topic_tag=data.get("topic_tag") or None,
            cue_hits=[str(c) for c in cue_hits],
            is_qa_answer=bool(data.get("is_qa_answer", False)),
            answered_question=data.get("answered_question") or None,
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
        memory: Optional SessionMemory for layered history (recent/topic/cue/qa).
            When None, the prompt falls back to the pre-memory structure.
    """

    def __init__(
        self,
        tts_queue: queue.Queue,
        tts_player: object,
        knowledge_ctx: str,
        llm_generate_fn,
        urgent_queue: queue.Queue | None = None,
        persona_ctx: str = "",
        memory: SessionMemory | None = None,
    ) -> None:
        self._tts_queue = tts_queue
        self._tts_player = tts_player
        self._knowledge_ctx = knowledge_ctx
        self._persona_ctx = persona_ctx
        self._llm_generate = llm_generate_fn
        self._urgent_queue = urgent_queue
        self._memory = memory
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
                script_state=script_state,
                knowledge_ctx=self._knowledge_ctx,
                recent_events=all_events,
                memory=self._memory,
                persona_ctx=self._persona_ctx,
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

        tts_item = self._tts_player.put(
            output.content, output.speech_prompt, urgent=bool(urgent_events)
        )
        if self._memory is not None:
            cue_list = script_state.get("cue") or []
            valid_cue_hits = [c for c in output.cue_hits if c in cue_list]
            utterance_id = getattr(tts_item, "id", "")
            self._memory.record_utterance(
                text=output.content,
                topic_tag=output.topic_tag,
                utterance_id=utterance_id,
                segment_id=script_state.get("segment_id"),
                cue_hits=valid_cue_hits,
            )
            if output.is_qa_answer and output.answered_question:
                self._memory.record_qa(output.answered_question, output.content)
        logger.info("[DIRECTOR] %s (%s): %s", output.source, output.reason, output.content[:60])
