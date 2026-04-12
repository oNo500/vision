"""CdpEventCollector — captures Douyin live danmu via Chrome DevTools Protocol.

Connects to a running Chrome instance (launched with --remote-debugging-port)
and listens for WebSocket frames on the Douyin live page. No proxy, no fake
requests, no certificates required.

Prerequisites:
    1. Launch Chrome with the remote debugging port enabled:
           open -a "Google Chrome" --args --remote-debugging-port=9222
    2. Open the Douyin live room in that Chrome window.
    3. Start the collector — it auto-discovers the live page tab.

Usage:
    collector = CdpEventCollector(out_queue=q, cdp_url="ws://localhost:9222")
    collector.start()
    ...
    collector.stop()

References:
    proto definitions: https://github.com/saermart/DouyinLiveWebFetcher
    Windows MITM alternative: https://github.com/HaoDong108/DouyinBarrageGrab
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import logging
import queue
import threading
import time
from typing import Any  # noqa: F401 — used in _build_user_info type hint

from src.live.proto_douyin import (
    ChatMessage,
    ControlMessage,
    FansclubMessage,
    GiftMessage,
    LikeMessage,
    MemberMessage,
    PushFrame,
    Response,
    RoomUserSeqMessage,
    SocialMessage,
)
from src.live.schema import Event, UserInfo

logger = logging.getLogger(__name__)

_DOUYIN_LIVE_HOST = "live.douyin.com"


class CdpEventCollector:
    """Reads live events from Douyin via CDP and puts them onto *out_queue*.

    Args:
        out_queue: Queue shared with the Orchestrator.
        cdp_url:   WebSocket URL of the Chrome DevTools endpoint.
                   Default: ws://localhost:9222
    """

    def __init__(
        self,
        out_queue: queue.Queue[Event],
        cdp_url: str = "http://localhost:9222",
    ) -> None:
        self._queue = out_queue
        self._cdp_url = cdp_url
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream_start: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public interface (mirrors DouyinEventCollector / MockEventCollector)
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._stream_start = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CdpCollector")
        self._thread.start()
        logger.info("CdpEventCollector started, cdp=%s", self._cdp_url)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Internal — threading bridge
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._listen())
        finally:
            loop.close()

    async def _listen(self) -> None:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(self._cdp_url)
            page = await self._find_live_page(browser)
            if page is None:
                logger.error("No Douyin live page found in Chrome. Open a live room first.")
                return

            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Network.enable")
            cdp.on("Network.webSocketFrameReceived", self._on_ws_frame)

            logger.info("Listening for WebSocket frames on: %s", page.url)

            # Keep alive until stop() is called
            while not self._stop_event.is_set():
                await asyncio.sleep(0.5)

            await cdp.detach()
            await browser.close()

    async def _find_live_page(self, browser: Any) -> Any:
        """Return the first page whose URL is a Douyin live room."""
        for context in browser.contexts:
            for page in context.pages:
                if _DOUYIN_LIVE_HOST in page.url:
                    return page
        return None

    # ------------------------------------------------------------------
    # Internal — CDP event handler
    # ------------------------------------------------------------------

    def _on_ws_frame(self, params: dict) -> None:
        payload_data = params.get("response", {}).get("payloadData", "")
        events = self._parse_frame(payload_data)
        t = time.monotonic() - self._stream_start
        for event in events:
            event.t = t
            self._queue.put(event)
            logger.info("[CDP] %s from %s", event.type, event.user)

    # ------------------------------------------------------------------
    # Internal — protobuf parsing (pure, testable without browser)
    # ------------------------------------------------------------------

    def _parse_frame(self, payload_data: str) -> list[Event]:
        """Decode a base64 WSS binary frame and return zero or more Events."""
        try:
            raw = base64.b64decode(payload_data)
            push_frame = PushFrame().parse(raw)
            if push_frame.payload_type not in ("msg", ""):
                return []
            response = Response().parse(gzip.decompress(push_frame.payload))
        except Exception as exc:
            logger.debug("Failed to decode frame: %s", exc)
            return []

        events: list[Event] = []
        for msg in response.messages_list:
            event = self._parse_message(msg.method, msg.payload)
            if event:
                events.append(event)
        return events

    @staticmethod
    def _build_user_info(u: Any) -> UserInfo:
        """Extract rich metadata from a proto User object."""
        fi = u.follow_info if u.follow_info else None
        pg = u.pay_grade if u.pay_grade else None
        fc = u.fans_club.data if (u.fans_club and u.fans_club.data) else None
        return UserInfo(
            uid=u.id,
            display_id=u.display_id,
            sec_uid=u.sec_uid,
            gender=u.gender,
            follow_status=fi.follow_status if fi else 0,
            follower_count=fi.follower_count if fi else 0,
            pay_grade=pg.level if pg else 0,
            fans_club_name=fc.club_name if fc else "",
            fans_club_level=fc.level if fc else 0,
        )

    def _parse_message(self, method: str, payload: bytes) -> Event | None:
        t = 0.0  # will be overwritten by _on_ws_frame
        try:
            if method == "WebcastChatMessage":
                m = ChatMessage().parse(payload)
                return Event(
                    type="danmaku",
                    user=m.user.nick_name,
                    t=t,
                    text=m.content,
                    user_info=self._build_user_info(m.user),
                    raw=m.to_dict(),
                )

            if method == "WebcastGiftMessage":
                m = GiftMessage().parse(payload)
                return Event(
                    type="gift",
                    user=m.user.nick_name,
                    t=t,
                    gift=m.gift.name,
                    value=m.gift.diamond_count,
                    combo_count=m.combo_count,
                    gift_count=m.repeat_count,
                    user_info=self._build_user_info(m.user),
                    raw=m.to_dict(),
                )

            if method == "WebcastMemberMessage":
                m = MemberMessage().parse(payload)
                ui = self._build_user_info(m.user)
                ui.is_admin = m.is_set_to_admin
                return Event(
                    type="enter",
                    user=m.user.nick_name,
                    t=t,
                    enter_type=m.enter_type,
                    user_info=ui,
                    raw=m.to_dict(),
                )

            if method == "WebcastLikeMessage":
                m = LikeMessage().parse(payload)
                return Event(
                    type="like",
                    user=m.user.nick_name,
                    t=t,
                    value=m.count,
                    user_info=self._build_user_info(m.user),
                    raw=m.to_dict(),
                )

            if method == "WebcastSocialMessage":
                m = SocialMessage().parse(payload)
                # action=1 → follow, action=3 → share
                event_type = "share" if m.action == 3 else "follow"
                return Event(
                    type=event_type,
                    user=m.user.nick_name,
                    t=t,
                    user_info=self._build_user_info(m.user),
                    raw=m.to_dict(),
                )

            if method == "WebcastFansclubMessage":
                m = FansclubMessage().parse(payload)
                return Event(
                    type="fansclub",
                    user=m.user.nick_name,
                    t=t,
                    text=m.content,
                    user_info=self._build_user_info(m.user),
                    raw=m.to_dict(),
                )

            if method == "WebcastRoomUserSeqMessage":
                m = RoomUserSeqMessage().parse(payload)
                return Event(
                    type="stats",
                    user="",
                    t=t,
                    value=m.total,
                    total_pv=m.total_pv_for_anchor,
                    raw=m.to_dict(),
                )

            if method == "WebcastControlMessage":
                m = ControlMessage().parse(payload)
                if m.status == 3:
                    return Event(type="end", user="", t=t)
                return None

        except Exception as exc:
            logger.debug("Failed to parse %s: %s", method, exc)

        return None
