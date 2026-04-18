"""Tests for EventBus pub/sub."""
import asyncio
import pytest
from vision_shared.event_bus import EventBus


@pytest.fixture
def bus():
    loop = asyncio.new_event_loop()
    b = EventBus(loop)
    yield b
    loop.close()


def test_subscribe_returns_queue(bus):
    q = bus.subscribe()
    assert q is not None


def test_unsubscribe_removes_queue(bus):
    q = bus.subscribe()
    bus.unsubscribe(q)
    # publish should not raise even with no subscribers
    bus.publish({"type": "test"})


def test_publish_delivers_to_subscriber(bus):
    loop = bus._loop
    q = bus.subscribe()
    event = {"type": "tts_output", "content": "hello"}
    bus.publish(event)
    # drain pending callbacks
    loop.run_until_complete(asyncio.sleep(0))
    result = q.get_nowait()
    assert result == event


def test_publish_fans_out_to_multiple_subscribers(bus):
    loop = bus._loop
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.publish({"type": "danmaku", "user": "A"})
    loop.run_until_complete(asyncio.sleep(0))
    assert q1.get_nowait()["type"] == "danmaku"
    assert q2.get_nowait()["type"] == "danmaku"


def test_publish_after_unsubscribe_does_not_deliver(bus):
    loop = bus._loop
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.publish({"type": "test"})
    loop.run_until_complete(asyncio.sleep(0))
    assert q.empty()
