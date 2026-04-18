"""Tests for Orchestrator — P0/P1 rule interrupt layer + buffering."""
from __future__ import annotations

import queue

from src.live.orchestrator import Orchestrator, classify_event
from src.live.schema import Event
from src.live.tts_player import TtsItem


# ---------------------------------------------------------------------------
# classify_event
# ---------------------------------------------------------------------------


def test_high_value_gift_is_p0():
    ev = Event(type="gift", user="A", gift="rocket", value=500, t=0)
    assert classify_event(ev) == "P0"


def test_low_value_gift_is_p3():
    ev = Event(type="gift", user="A", gift="heart", value=1, t=0)
    assert classify_event(ev) == "P3"


def test_follower_enter_is_p1():
    ev = Event(type="enter", user="A", t=0, is_follower=True)
    assert classify_event(ev) == "P1"


def test_non_follower_enter_is_p3():
    ev = Event(type="enter", user="A", t=0, is_follower=False)
    assert classify_event(ev) == "P3"


def test_question_danmaku_is_p2():
    ev = Event(type="danmaku", user="A", text="怎么买？", t=0)
    assert classify_event(ev) == "P2"


def test_plain_danmaku_is_p3():
    ev = Event(type="danmaku", user="A", text="加油", t=0)
    assert classify_event(ev) == "P3"


# ---------------------------------------------------------------------------
# immediate strategy: P0/P1 → tts queue with template text
# ---------------------------------------------------------------------------


def _state() -> dict:
    return {"finished": False}


def test_p0_gift_enqueues_immediate_tts():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    ev = Event(type="gift", user="Alice", gift="rocket", value=500, t=0)
    orch.handle_event(ev, _state())
    item = tts_q.get_nowait()
    assert "Alice" in item.text
    assert "rocket" in item.text


def test_p1_follower_enter_enqueues_welcome_tts():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    ev = Event(type="enter", user="Bob", is_follower=True, t=0)
    orch.handle_event(ev, _state())
    item = tts_q.get_nowait()
    assert "Bob" in item.text


# ---------------------------------------------------------------------------
# P2/P3 → buffer
# ---------------------------------------------------------------------------


def test_question_danmaku_goes_to_buffer():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    ev = Event(type="danmaku", user="A", text="怎么买？", t=0)
    orch.handle_event(ev, _state())
    assert tts_q.empty()
    assert orch.buffer_size == 1


def test_get_events_clears_buffer_by_default():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    orch.handle_event(Event(type="danmaku", user="A", text="hi", t=0), _state())
    orch.handle_event(Event(type="danmaku", user="B", text="hey", t=0), _state())

    events = orch.get_events()
    assert len(events) == 2
    assert orch.buffer_size == 0


def test_get_events_without_clear_keeps_buffer():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    orch.handle_event(Event(type="danmaku", user="A", text="hi", t=0), _state())
    orch.get_events(clear=False)
    assert orch.buffer_size == 1


def test_finished_state_drops_events():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    orch.handle_event(
        Event(type="gift", user="A", gift="rocket", value=500, t=0),
        {"finished": True},
    )
    assert tts_q.empty()
    assert orch.buffer_size == 0


# ---------------------------------------------------------------------------
# intelligent strategy: P0/P1 → urgent_queue
# ---------------------------------------------------------------------------


def test_intelligent_strategy_routes_p0_to_urgent_queue():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    urgent_q: queue.Queue[Event] = queue.Queue()
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "intelligent",
        urgent_queue=urgent_q,
    )
    ev = Event(type="gift", user="A", gift="rocket", value=500, t=0)
    orch.handle_event(ev, _state())

    assert tts_q.empty()
    queued = urgent_q.get_nowait()
    assert queued.user == "A"


def test_immediate_strategy_does_not_touch_urgent_queue():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    urgent_q: queue.Queue[Event] = queue.Queue()
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "immediate",
        urgent_queue=urgent_q,
    )
    ev = Event(type="gift", user="A", gift="rocket", value=500, t=0)
    orch.handle_event(ev, _state())

    assert not tts_q.empty()
    assert urgent_q.empty()


def test_full_urgent_queue_drops_event_without_raising():
    tts_q: queue.Queue[TtsItem] = queue.Queue()
    urgent_q: queue.Queue[Event] = queue.Queue(maxsize=1)
    urgent_q.put(Event(type="gift", user="pad", t=0))   # saturate
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "intelligent",
        urgent_queue=urgent_q,
    )
    # Must not raise
    orch.handle_event(
        Event(type="gift", user="A", gift="rocket", value=500, t=0),
        _state(),
    )
    assert urgent_q.qsize() == 1   # still just the padding item
    assert tts_q.empty()
