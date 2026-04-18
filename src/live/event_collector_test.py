"""Tests for MockEventCollector scripted-timeline replay."""
from __future__ import annotations

import queue
import time

from src.live.event_collector import MockEventCollector
from src.live.schema import Event


def _collect(events: list[dict], speed: float = 100.0, wait: float = 0.3) -> list[Event]:
    """Run the collector at high speed and drain the queue."""
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(events, q, speed=speed)
    collector.start()
    time.sleep(wait)
    collector.stop()
    drained: list[Event] = []
    while not q.empty():
        drained.append(q.get_nowait())
    return drained


def test_emits_all_events_in_timestamp_order():
    events = [
        {"type": "danmaku", "user": "Alice", "t": 0.2, "text": "hi"},
        {"type": "danmaku", "user": "Bob", "t": 0.1, "text": "hello"},
    ]
    out = _collect(events)
    assert [e.user for e in out] == ["Bob", "Alice"]


def test_event_types_preserved():
    events = [
        {"type": "danmaku", "user": "U", "t": 0.0, "text": "x"},
        {"type": "gift", "user": "V", "t": 0.05, "gift": "rocket", "value": 500},
        {"type": "enter", "user": "W", "t": 0.10, "is_follower": True},
    ]
    out = _collect(events)
    assert [e.type for e in out] == ["danmaku", "gift", "enter"]


def test_gift_fields_populated():
    events = [{"type": "gift", "user": "V", "t": 0.0, "gift": "rocket", "value": 500}]
    out = _collect(events)
    assert out[0].gift == "rocket"
    assert out[0].value == 500


def test_danmaku_text_populated():
    events = [{"type": "danmaku", "user": "U", "t": 0.0, "text": "hello world"}]
    out = _collect(events)
    assert out[0].text == "hello world"


def test_is_follower_flag_preserved():
    events = [
        {"type": "enter", "user": "A", "t": 0.0, "is_follower": True},
        {"type": "enter", "user": "B", "t": 0.05, "is_follower": False},
    ]
    out = _collect(events)
    assert out[0].is_follower is True
    assert out[1].is_follower is False


def test_empty_event_list_stops_cleanly():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector([], q)
    collector.start()
    collector.stop()
    assert q.empty()


def test_stop_is_idempotent():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector([], q)
    collector.start()
    collector.stop()
    collector.stop()   # must not raise


def test_stop_during_replay_halts_emission():
    events = [{"type": "danmaku", "user": f"u{i}", "t": i * 0.5, "text": "x"} for i in range(10)]
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(events, q, speed=1.0)
    collector.start()
    time.sleep(0.1)
    collector.stop()
    # should have emitted at most 1 before stop
    drained = []
    while not q.empty():
        drained.append(q.get_nowait())
    assert len(drained) <= 1
