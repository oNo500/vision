"""EventCollector — emits Events into a queue.

MockEventCollector replays a scripted timeline at a configurable speed
multiplier. Replace this class with a real WebSocket client when connecting
to a live platform.
"""
from __future__ import annotations

import logging
import queue
import threading
import time

from scripts.live.schema import Event

logger = logging.getLogger(__name__)


class MockEventCollector:
    """Replays a list of mock events onto a queue, respecting their `t` timestamps.

    Args:
        events: List of event dicts with at minimum ``type``, ``user``, ``t``.
        out_queue: Queue to put Event objects onto.
        speed: Time multiplier. ``speed=2.0`` replays twice as fast.
    """

    def __init__(
        self,
        events: list[dict],
        out_queue: queue.Queue[Event],
        speed: float = 1.0,
    ) -> None:
        self._events = sorted(events, key=lambda e: e["t"])
        self._queue = out_queue
        self._speed = speed
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start replaying events in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="EventCollector")
        self._thread.start()
        logger.info("EventCollector started (speed=%.1fx)", self._speed)

    def stop(self) -> None:
        """Stop the replay thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        stream_start = time.monotonic()
        for ev in self._events:
            if self._stop_event.is_set():
                break
            target_wall = ev["t"] / self._speed
            now = time.monotonic() - stream_start
            delay = target_wall - now
            if delay > 0:
                self._stop_event.wait(timeout=delay)
            if self._stop_event.is_set():
                break
            event = Event(
                type=ev["type"],
                user=ev["user"],
                t=ev["t"],
                text=ev.get("text"),
                gift=ev.get("gift"),
                value=ev.get("value", 0),
                is_follower=ev.get("is_follower", False),
            )
            self._queue.put(event)
            logger.info("[EVENT] %s from %s", event.type, event.user)
        logger.info("EventCollector finished replay")
