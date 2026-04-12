"""Tests for DouyinEventCollector.

These tests spin up a real local WebSocket server to simulate the hub,
so no mitmproxy or Douyin connection is needed.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time

import pytest

from scripts.live.douyin_collector import DouyinEventCollector
from scripts.live.schema import Event

# Use a different port from the production hub to avoid conflicts.
_TEST_PORT = 2537


def _run_fake_hub(port: int, messages: list[str], stop: threading.Event) -> None:
    """Serve messages to the first connecting client, then idle."""

    async def _serve() -> None:
        import websockets  # type: ignore[import-untyped]

        async def _handler(ws: object) -> None:
            for msg in messages:
                await ws.send(msg)  # type: ignore[attr-defined]
            # Keep connection open until stop is set
            while not stop.is_set():
                await asyncio.sleep(0.05)

        async with websockets.serve(_handler, "127.0.0.1", port):
            while not stop.is_set():
                await asyncio.sleep(0.05)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_serve())
    loop.close()


def _make_hub_messages() -> list[str]:
    return [
        json.dumps({"Cmd": "WebcastChatMessage", "Data": {"user": "Alice", "content": "hello"}}),
        json.dumps({"Cmd": "WebcastGiftMessage", "Data": {"user": "Bob", "gift": {"name": "rocket", "diamondCount": 500}}}),
        json.dumps({"Cmd": "WebcastMemberMessage", "Data": {"user": "Carol"}}),
        json.dumps({"Cmd": "WebcastLikeMessage", "Data": {"user": "Dave", "count": 5}}),
    ]


@pytest.fixture()
def fake_hub():
    """Fixture: start a fake hub, yield, then stop."""
    stop = threading.Event()
    msgs = _make_hub_messages()
    t = threading.Thread(target=_run_fake_hub, args=(_TEST_PORT, msgs, stop), daemon=True)
    t.start()
    time.sleep(0.2)  # let the server bind
    yield
    stop.set()
    t.join(timeout=2)


def _collect(port: int, timeout: float = 1.5) -> list[Event]:
    q: queue.Queue[Event] = queue.Queue()
    collector = DouyinEventCollector(out_queue=q, hub_port=port)
    collector.start()
    time.sleep(timeout)
    collector.stop()
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


def test_danmaku_event(fake_hub):
    events = _collect(_TEST_PORT)
    danmaku = [e for e in events if e.type == "danmaku" and e.text == "hello"]
    assert danmaku, "Expected a danmaku event with text='hello'"
    assert danmaku[0].user == "Alice"


def test_gift_event(fake_hub):
    events = _collect(_TEST_PORT)
    gifts = [e for e in events if e.type == "gift"]
    assert gifts, "Expected a gift event"
    assert gifts[0].gift == "rocket"
    assert gifts[0].value == 500
    assert gifts[0].user == "Bob"


def test_enter_event(fake_hub):
    events = _collect(_TEST_PORT)
    enters = [e for e in events if e.type == "enter"]
    assert enters, "Expected an enter event"
    assert enters[0].user == "Carol"


def test_like_mapped_to_danmaku(fake_hub):
    events = _collect(_TEST_PORT)
    likes = [e for e in events if e.type == "danmaku" and "点赞" in (e.text or "")]
    assert likes, "Expected a like event mapped to danmaku"
    assert likes[0].user == "Dave"


def test_stop_is_idempotent(fake_hub):
    q: queue.Queue[Event] = queue.Queue()
    collector = DouyinEventCollector(out_queue=q, hub_port=_TEST_PORT)
    collector.start()
    time.sleep(0.2)
    collector.stop()
    collector.stop()  # should not raise


def test_reconnects_when_hub_unavailable():
    """Collector should not crash when hub is not up yet; it retries."""
    q: queue.Queue[Event] = queue.Queue()
    # Use a port with nothing listening
    collector = DouyinEventCollector(out_queue=q, hub_port=2599)
    collector.start()
    time.sleep(0.5)  # let it attempt a couple of reconnects
    collector.stop()  # must not raise
