"""Tests for mock event collector."""
import queue
import time

from src.live.event_collector import MockEventCollector
from src.live.schema import Event

MOCK_EVENTS = [
    {"type": "enter", "user": "Alice", "is_follower": True, "t": 0.0},
    {"type": "danmaku", "user": "Bob", "text": "hello", "t": 0.1},
    {"type": "gift", "user": "Carol", "gift": "rocket", "value": 500, "t": 0.2},
]


def test_collector_emits_all_events():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    time.sleep(0.5)
    collector.stop()
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    assert len(events) == 3


def test_event_types_correct():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    time.sleep(0.5)
    collector.stop()
    types = []
    while not q.empty():
        types.append(q.get_nowait().type)
    assert types == ["enter", "danmaku", "gift"]


def test_event_fields_populated():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    time.sleep(0.5)
    collector.stop()
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    gift_event = events[2]
    assert gift_event.gift == "rocket"
    assert gift_event.value == 500


def test_stop_is_idempotent():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    collector.stop()
    collector.stop()   # should not raise
