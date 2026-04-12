"""DouyinEventCollector — connects to the DouyinBarrageGrab WebSocket service.

Drop-in replacement for MockEventCollector with the same start()/stop() interface.

Prerequisites (Windows only):
    1. Download and run DouyinBarrageGrab as Administrator:
           https://github.com/ape-byte/DouyinBarrageGrab/releases
    2. Open a Douyin live room in Chrome — verify events scroll in the console.
    3. Start the agent with --douyin flag.

Then instantiate this collector instead of MockEventCollector:
    collector = DouyinEventCollector(out_queue=q)
    collector.start()
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time

from src.live.schema import Event

logger = logging.getLogger(__name__)

_HUB_HOST = "127.0.0.1"
_HUB_PORT = 8888  # DouyinBarrageGrab default WebSocket port

# Seconds between reconnect attempts when the hub is not yet up.
_RECONNECT_DELAY = 2.0


class DouyinEventCollector:
    """Reads live events from the local WS hub and puts them onto *out_queue*.

    Args:
        out_queue: Queue shared with the Orchestrator.
        hub_host:  Host of the local WS hub (default: 127.0.0.1).
        hub_port:  Port of the local WS hub (default: 2536).
    """

    def __init__(
        self,
        out_queue: queue.Queue[Event],
        hub_host: str = _HUB_HOST,
        hub_port: int = _HUB_PORT,
    ) -> None:
        self._queue = out_queue
        self._hub_url = f"ws://{hub_host}:{hub_port}"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream_start: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public interface (mirrors MockEventCollector)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background receiver thread."""
        self._stream_start = time.monotonic()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="DouyinCollector"
        )
        self._thread.start()
        logger.info("DouyinEventCollector started, hub=%s", self._hub_url)

    def stop(self) -> None:
        """Signal the receiver thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_with_retry())
        finally:
            loop.close()

    async def _connect_with_retry(self) -> None:
        import websockets  # type: ignore[import-untyped]

        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self._hub_url) as ws:
                    logger.info("Connected to hub %s", self._hub_url)
                    async for raw in ws:
                        if self._stop_event.is_set():
                            return
                        self._handle_message(raw)
            except (OSError, Exception) as exc:
                if self._stop_event.is_set():
                    return
                logger.warning("Hub not reachable (%s), retrying in %.0fs", exc, _RECONNECT_DELAY)
                await asyncio.sleep(_RECONNECT_DELAY)

    def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Non-JSON message: %s", raw[:80])
            return

        cmd: str = msg.get("Cmd", "")
        data: dict = msg.get("Data", {})
        event = self._to_event(cmd, data)
        if event:
            self._queue.put(event)
            logger.info("[DOUYIN] %s from %s", event.type, event.user)

    def _to_event(self, cmd: str, data: dict) -> Event | None:
        t = time.monotonic() - self._stream_start
        user: str = data.get("user", "unknown")

        if cmd == "WebcastChatMessage":
            return Event(type="danmaku", user=user, t=t, text=data.get("content"))

        if cmd == "WebcastGiftMessage":
            gift_info: dict = data.get("gift", {})
            return Event(
                type="gift",
                user=user,
                t=t,
                gift=gift_info.get("name"),
                value=gift_info.get("diamondCount", 0),
            )

        if cmd == "WebcastMemberMessage":
            return Event(type="enter", user=user, t=t)

        if cmd == "WebcastLikeMessage":
            # Extend schema if you want to handle likes separately;
            # for now map to a lightweight danmaku-style event.
            return Event(type="danmaku", user=user, t=t, text=f"[点赞 x{data.get('count', 1)}]")

        # Unknown / raw_frame — ignore silently
        return None
