"""EventBus — thread-safe pub/sub bridging sync Agent threads to async SSE handlers."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """Fan-out bus: sync threads publish; async SSE handlers subscribe.

    Args:
        loop: The running asyncio event loop (set during FastAPI lifespan).
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Return a new per-connection queue. Call from the async SSE handler."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue. Call on client disconnect."""
        self._subscribers.discard(q)

    def publish(self, event: dict) -> None:
        """Publish event to all subscribers. Safe to call from any thread."""
        def _put():
            for q in list(self._subscribers):
                q.put_nowait(event)

        self._loop.call_soon_threadsafe(_put)
