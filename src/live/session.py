"""SessionManager — owns AI Agent lifecycle and wires EventBus callbacks."""
from __future__ import annotations

import logging
import queue
import time
import threading
from typing import Any

from src.live.director_agent import DirectorAgent
from src.live.knowledge_base import KnowledgeBase
from src.live.script_runner import ScriptRunner
from src.live.tts_player import TTSPlayer, TtsItem
from src.shared.event_bus import EventBus
from src.shared.ordered_item_store import OrderedItemStore

logger = logging.getLogger(__name__)


def _build_persona_ctx(persona: dict) -> str:
    """Build a persona context string for the director prompt."""
    parts = [f"主播：{persona.get('name', '')}"]
    if persona.get("style"):
        parts.append(f"风格：{persona['style']}")
    if persona.get("catchphrases"):
        parts.append(f"口头禅：{'、'.join(persona['catchphrases'])}")
    if persona.get("forbidden_words"):
        parts.append(f"禁用词：{'、'.join(persona['forbidden_words'])}")
    return " | ".join(parts)


def _build_knowledge_ctx_from_plan(product: dict) -> str:
    """Build a knowledge context string from plan product data."""
    lines = [
        f"【产品】{product.get('name', '')} — {product.get('description', '')}",
        f"【价格】¥{product.get('price', '')}",
        "【亮点】",
    ]
    for h in product.get("highlights", []):
        lines.append(f"  - {h}")
    lines.append("【常见问题】")
    for faq in product.get("faq", []):
        lines.append(f"  Q: {faq.get('question', '')}")
        lines.append(f"  A: {faq.get('answer', '')}")
    return "\n".join(lines)


class SessionAlreadyRunningError(RuntimeError):
    pass


class SessionManager:
    """Manages a single live AI Agent session (AI components only).

    Wires EventBus.publish into Agent components as callbacks without
    modifying their internals. Danmaku/event components live in DanmakuManager.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = threading.Lock()
        self._components: list[Any] = []
        self._script_runner: ScriptRunner | None = None
        self._tts_player: TTSPlayer | None = None
        self._director: DirectorAgent | None = None
        self._tts_queue: OrderedItemStore | None = None
        self._urgent_queue: queue.Queue | None = None
        self._broadcaster_stop: threading.Event = threading.Event()
        self._strategy: str = "immediate"
        self._active_plan: dict | None = None

    def start(
        self,
        script_path: str,
        product_path: str,
        mock: bool,
        project: str | None,
    ) -> None:
        with self._lock:
            if self._running:
                raise SessionAlreadyRunningError("Session already running")
            self._running = True

        try:
            self._build_and_start(script_path, product_path, mock, project)
        except Exception:
            with self._lock:
                self._running = False
                self._tts_queue = None
                self._urgent_queue = None
            raise

        self._bus.publish({"type": "agent", "status": "started", "ts": time.time()})
        logger.info("SessionManager: agent started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                raise RuntimeError("Session not running")
            self._running = False

        for component in reversed(self._components):
            try:
                component.stop()
            except Exception as e:
                logger.warning("Error stopping component %s: %s", component, e)
        self._components.clear()
        self._broadcaster_stop.set()
        self._script_runner = None
        self._tts_player = None
        self._director = None
        self._tts_queue = None
        self._urgent_queue = None
        self._bus.publish({"type": "agent", "status": "stopped", "ts": time.time()})
        logger.info("SessionManager: agent stopped")

    def inject(self, content: str, speech_prompt: str | None) -> None:
        with self._lock:
            if not self._running:
                raise RuntimeError("Session not running")
            tts_player = self._tts_player
        tts_player.put(content, speech_prompt)

    def get_script_runner(self) -> ScriptRunner | None:
        with self._lock:
            return self._script_runner if self._running else None

    def get_state(self) -> dict:
        with self._lock:
            running = self._running
            script_runner = self._script_runner
            tts_queue = self._tts_queue
            urgent_queue = self._urgent_queue
            tts_player = self._tts_player
            director = self._director
            strategy = self._strategy
        if not running or script_runner is None:
            return {"running": False, "strategy": strategy}
        state = script_runner.get_state()
        # tts_queue.qsize() only counts items not yet picked up by the synth thread.
        # Use director.pending_depth which includes in-flight LLM calls + tts_queue.
        return {
            "running": True,
            "tts_queue_depth": (tts_queue.qsize() + tts_player._pcm_queue.qsize()) if tts_queue else 0,
            "urgent_queue_depth": urgent_queue.qsize() if urgent_queue else 0,
            "tts_speaking": tts_player.is_speaking if tts_player else False,
            "llm_generating": director.is_generating if director else False,
            "strategy": strategy,
            **state,
        }

    def get_tts_queue_snapshot(self) -> list[dict]:
        """Return a snapshot of pending TtsItems for the front-end queue panel.

        Includes items in both in_queue (waiting for synthesis) and pcm_queue
        (synthesized, waiting for playback) for an accurate picture.
        """
        with self._lock:
            if not self._running:
                return []
            q = self._tts_queue
            player = self._tts_player
        if q is None or player is None:
            return []
        text_items = [i for i in list(q.queue) if isinstance(i, TtsItem)]
        pcm_items = [i for i in list(player._pcm_queue.queue) if hasattr(i, "id")]
        all_items = text_items + pcm_items
        return [
            {"id": item.id, "content": item.text, "speech_prompt": item.speech_prompt}
            for item in all_items
        ]

    def get_strategy(self) -> str:
        with self._lock:
            return self._strategy

    def set_strategy(self, strategy: str) -> None:
        if strategy not in ("immediate", "intelligent"):
            raise ValueError(f"Unknown strategy: {strategy}")
        with self._lock:
            self._strategy = strategy

    def load_plan(self, plan: dict) -> None:
        with self._lock:
            self._active_plan = plan

    def get_active_plan(self) -> dict | None:
        with self._lock:
            return self._active_plan

    def get_tts_queue(self) -> "OrderedItemStore | None":
        with self._lock:
            return self._tts_queue if self._running else None

    def get_urgent_queue(self) -> "queue.Queue | None":
        with self._lock:
            return self._urgent_queue if self._running else None

    def _build_and_start(
        self,
        script_path: str,
        product_path: str,
        mock: bool,
        project: str | None,
    ) -> None:
        tts_queue: OrderedItemStore[TtsItem] = OrderedItemStore()
        urgent_queue: queue.Queue = queue.Queue(maxsize=10)
        self._tts_queue = tts_queue
        self._urgent_queue = urgent_queue

        # Derive context from loaded plan or fall back to file-based sources
        active_plan = self._active_plan
        if active_plan:
            knowledge_ctx = _build_knowledge_ctx_from_plan(active_plan.get("product", {}))
            persona_ctx = _build_persona_ctx(active_plan.get("persona", {}))
            from src.live.schema import LiveScript, ScriptSegment
            segments_data = active_plan.get("script", {}).get("segments", [])
            live_script = LiveScript(
                title=active_plan["name"],
                total_duration=sum(s.get("duration", 0) for s in segments_data),
                segments=[
                    ScriptSegment(
                        id=s["id"],
                        title=s.get("title", f"段落{i + 1}"),
                        goal=s.get("goal", ""),
                        duration=s["duration"],
                        cue=s.get("cue", []),
                        must_say=s.get("must_say", False),
                        keywords=s.get("keywords", []),
                    )
                    for i, s in enumerate(segments_data)
                ],
            )
            script_runner = ScriptRunner(live_script)
        else:
            kb = KnowledgeBase(product_path)
            knowledge_ctx = kb.context_for_prompt()
            persona_ctx = ""
            script_runner = ScriptRunner.from_yaml(script_path)

        if mock:
            import json as _json

            def llm_generate(prompt: str) -> str:
                return _json.dumps({
                    "content": "大家好，今天给大家带来好产品！",
                    "speech_prompt": "热情自然地介绍",
                    "source": "script",
                    "reason": "mock",
                }, ensure_ascii=False)
        else:
            if not project:
                raise ValueError("project required in production mode")
            import vertexai
            from vertexai.generative_models import GenerativeModel
            from src.live.director_agent import _SYSTEM_PROMPT
            vertexai.init(project=project, location="us-central1")
            _model = GenerativeModel(model_name="gemini-2.5-flash", system_instruction=_SYSTEM_PROMPT)

            def llm_generate(prompt: str) -> str:
                return _model.generate_content(prompt).text

        speak_fn = (lambda text, prompt=None: logger.info("[TTS MOCK] %s", text)) if mock else None

        def get_events_fn() -> list:
            return []  # No Orchestrator — DanmakuManager wires this separately

        def _on_queued(item: TtsItem) -> None:
            self._bus.publish({
                "type": "tts_queued",
                "id": item.id,
                "content": item.text,
                "speech_prompt": item.speech_prompt,
                "ts": time.time(),
            })

        def _on_play(item: TtsItem) -> None:
            self._bus.publish({
                "type": "tts_playing",
                "id": item.id,
                "content": item.text,
                "speech_prompt": item.speech_prompt,
                "ts": time.time(),
            })

        def _on_done(item: TtsItem) -> None:
            self._bus.publish({
                "type": "tts_done",
                "id": item.id,
                "ts": time.time(),
            })

        tts_player = TTSPlayer(
            tts_queue,
            speak_fn=speak_fn,
            on_queued=_on_queued,
            on_play=_on_play,
            on_done=_on_done,
            google_cloud_project=project,
        )
        director = DirectorAgent(
            tts_queue=tts_queue,
            tts_player=tts_player,
            knowledge_ctx=knowledge_ctx,
            llm_generate_fn=llm_generate,
            urgent_queue=urgent_queue,
            persona_ctx=persona_ctx,
        )

        self._script_runner = script_runner
        self._tts_player = tts_player
        self._director = director

        script_runner.start()
        tts_player.start()
        director.start(
            get_state_fn=script_runner.get_state,
            get_events_fn=get_events_fn,
        )

        self._components = [script_runner, tts_player, director]

        self._broadcaster_stop.clear()

        def _broadcast_script_state():
            while not self._broadcaster_stop.wait(timeout=5.0):
                state = script_runner.get_state()
                self._bus.publish({
                    "type": "script",
                    "segment_id": state.get("segment_id"),
                    "remaining_seconds": state.get("remaining_seconds", 0),
                    "segment_duration": state.get("segment_duration", 0),
                    "finished": state.get("finished", False),
                    "ts": time.time(),
                })

        broadcaster = threading.Thread(target=_broadcast_script_state, daemon=True, name="ScriptBroadcaster")
        broadcaster.start()
