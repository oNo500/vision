"""SessionManager — owns Agent lifecycle and wires EventBus callbacks."""
from __future__ import annotations

import logging
import queue
import time
import threading
from typing import Any

from src.live.director_agent import DirectorAgent
from src.live.event_collector import MockEventCollector
from src.live.knowledge_base import KnowledgeBase
from src.live.orchestrator import Orchestrator
from src.live.schema import Event
from src.live.script_runner import ScriptRunner
from src.live.tts_player import TTSPlayer, _SENTINEL as _TTS_SENTINEL
from src.shared.event_bus import EventBus

logger = logging.getLogger(__name__)


class SessionAlreadyRunningError(RuntimeError):
    pass


class SessionManager:
    """Manages a single live Agent session.

    Wires EventBus.publish into Agent components as callbacks without
    modifying their internals.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = threading.Lock()
        self._components: list[Any] = []
        self._script_runner: ScriptRunner | None = None
        self._orchestrator: Orchestrator | None = None
        self._tts_queue: queue.Queue | None = None
        self._broadcaster_stop: threading.Event = threading.Event()

    def start(
        self,
        script_path: str,
        product_path: str,
        mock: bool,
        project: str | None,
        cdp_url: str | None = None,
    ) -> None:
        with self._lock:
            if self._running:
                raise SessionAlreadyRunningError("Session already running")
            self._running = True

        try:
            self._build_and_start(script_path, product_path, mock, project, cdp_url)
        except Exception:
            with self._lock:
                self._running = False
                self._tts_queue = None
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
        self._orchestrator = None
        self._tts_queue = None
        self._bus.publish({"type": "agent", "status": "stopped", "ts": time.time()})
        logger.info("SessionManager: agent stopped")

    def inject(self, content: str, speech_prompt: str | None) -> None:
        with self._lock:
            if not self._running:
                raise RuntimeError("Session not running")
        self._tts_queue.put((content, speech_prompt))
        self._bus.publish({
            "type": "tts_output",
            "content": content,
            "speech_prompt": speech_prompt,
            "source": "inject",
            "ts": time.time(),
        })

    def get_state(self) -> dict:
        with self._lock:
            running = self._running
            script_runner = self._script_runner
            tts_queue = self._tts_queue
        if not running or script_runner is None:
            return {"running": False}
        state = script_runner.get_state()
        return {
            "running": True,
            "queue_depth": tts_queue.qsize() if tts_queue else 0,
            **state,
        }

    def _build_and_start(
        self,
        script_path: str,
        product_path: str,
        mock: bool,
        project: str | None,
        cdp_url: str | None = None,
    ) -> None:
        event_queue: queue.Queue[Event] = queue.Queue()
        tts_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._tts_queue = tts_queue

        kb = KnowledgeBase(product_path)

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

        if mock:
            def speak_fn(text: str, speech_prompt: str | None = None) -> None:
                logger.info("[TTS MOCK] %s", text)
        else:
            speak_fn = None

        script_runner = ScriptRunner.from_yaml(script_path)
        if cdp_url:
            from src.live.cdp_collector import CdpEventCollector
            event_collector = CdpEventCollector(out_queue=event_queue, cdp_url=cdp_url)
            logger.info("Using CdpEventCollector (cdp=%s)", cdp_url)
        else:
            event_collector = MockEventCollector([], event_queue)
        orchestrator = Orchestrator(tts_queue=tts_queue)
        tts_player = TTSPlayer(tts_queue, speak_fn=speak_fn)
        director = DirectorAgent(
            tts_queue=tts_queue,
            tts_player=tts_player,
            knowledge_ctx=kb.context_for_prompt(),
            llm_generate_fn=llm_generate,
        )

        # Wire EventBus callbacks by wrapping queue.put methods
        original_tts_put = tts_queue.put

        def _tts_put_with_publish(item, *args, **kwargs):
            original_tts_put(item, *args, **kwargs)
            content, speech_prompt = item
            if content is _TTS_SENTINEL:
                return
            self._bus.publish({
                "type": "tts_output",
                "content": content,
                "speech_prompt": speech_prompt,
                "source": "agent",
                "ts": time.time(),
            })

        tts_queue.put = _tts_put_with_publish

        original_eq_put = event_queue.put

        def _event_put_with_publish(event: Event, *args, **kwargs):
            original_eq_put(event, *args, **kwargs)
            state = script_runner.get_state()
            orchestrator.handle_event(event, state)   # route P0/P1 to TTS, P2/P3 to buffer
            self._bus.publish({
                "type": event.type,
                "user": event.user,
                "text": event.text,
                "gift": event.gift,
                "value": event.value,
                "is_follower": event.is_follower,
                "ts": time.time(),
            })

        event_queue.put = _event_put_with_publish

        self._script_runner = script_runner
        self._orchestrator = orchestrator

        script_runner.start()
        event_collector.start()
        tts_player.start()
        director.start(
            get_state_fn=script_runner.get_state,
            get_events_fn=orchestrator.get_events,
        )

        self._components = [script_runner, event_collector, tts_player, director]

        # Script state broadcaster thread
        self._broadcaster_stop.clear()

        def _broadcast_script_state():
            while not self._broadcaster_stop.wait(timeout=5.0):
                state = script_runner.get_state()
                self._bus.publish({
                    "type": "script",
                    "segment_id": state.get("segment_id"),
                    "remaining_seconds": state.get("remaining_seconds", 0),
                    "ts": time.time(),
                })

        broadcaster = threading.Thread(target=_broadcast_script_state, daemon=True, name="ScriptBroadcaster")
        broadcaster.start()
