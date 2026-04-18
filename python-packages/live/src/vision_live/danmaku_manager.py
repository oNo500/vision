"""DanmakuManager — owns EventCollector and Orchestrator."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable

from vision_live.event_collector import MockEventCollector
from vision_live.orchestrator import Orchestrator
from vision_live.schema import Event
from vision_shared.event_bus import EventBus

logger = logging.getLogger(__name__)


class DanmakuManager:
    """Manages danmaku collection and event routing independently of the AI session."""

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = threading.Lock()
        self._components: list[Any] = []
        self._orchestrator: Orchestrator | None = None

    def start(
        self,
        mock: bool,
        cdp_url: str | None,
        tts_queue: queue.Queue | None,
        get_strategy_fn: Callable[[], str],
        urgent_queue: queue.Queue | None,
    ) -> None:
        with self._lock:
            if self._running:
                raise RuntimeError("DanmakuManager already running")
            self._running = True

        try:
            self._build_and_start(mock, cdp_url, tts_queue, get_strategy_fn, urgent_queue)
        except Exception:
            with self._lock:
                self._running = False
            raise

        self._bus.publish({"type": "agent", "status": "danmaku_started", "ts": time.time()})
        logger.info("DanmakuManager: started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                raise RuntimeError("DanmakuManager not running")
            self._running = False
            self._orchestrator = None

        for component in reversed(self._components):
            try:
                component.stop()
            except Exception as e:
                logger.warning("Error stopping component %s: %s", component, e)
        self._components.clear()
        self._bus.publish({"type": "agent", "status": "danmaku_stopped", "ts": time.time()})
        logger.info("DanmakuManager: stopped")

    def get_state(self) -> dict:
        with self._lock:
            running = self._running
            orchestrator = self._orchestrator
        if not running or orchestrator is None:
            return {"running": False, "buffer_size": 0}
        return {"running": True, "buffer_size": orchestrator.buffer_size}

    def get_orchestrator(self) -> Orchestrator | None:
        with self._lock:
            return self._orchestrator if self._running else None

    def _build_and_start(
        self,
        mock: bool,
        cdp_url: str | None,
        tts_queue: queue.Queue | None,
        get_strategy_fn: Callable[[], str],
        urgent_queue: queue.Queue | None,
    ) -> None:
        event_queue: queue.Queue[Event] = queue.Queue()

        # Use a no-op queue if no TTS session running
        effective_tts_queue: queue.Queue = tts_queue if tts_queue is not None else queue.Queue()

        orchestrator = Orchestrator(
            tts_queue=effective_tts_queue,
            get_strategy_fn=get_strategy_fn,
            urgent_queue=urgent_queue,
        )

        if not mock and cdp_url:
            from vision_live.cdp_collector import CdpEventCollector
            event_collector = CdpEventCollector(out_queue=event_queue, cdp_url=cdp_url)
            logger.info("DanmakuManager: using CdpEventCollector (cdp=%s)", cdp_url)
        else:
            event_collector = MockEventCollector([], event_queue)

        def _event_put_with_publish(event: Event, *args, **kwargs):
            queue.Queue.put(event_queue, event, *args, **kwargs)
            orchestrator.handle_event(event, {"finished": False})
            self._bus.publish({
                "type": event.type,
                "user": event.user,
                "text": event.text,
                "gift": event.gift,
                "value": event.value,
                "is_follower": event.is_follower,
                "ts": time.time(),
            })

        event_queue.put = _event_put_with_publish  # type: ignore[method-assign]

        self._orchestrator = orchestrator
        event_collector.start()
        self._components = [event_collector]
