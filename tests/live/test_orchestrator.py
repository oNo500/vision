"""Tests for Orchestrator P0/P1 rule interrupt layer."""
import queue

from src.live.orchestrator import Orchestrator, classify_event
from src.live.schema import Event

INTERRUPTIBLE_STATE = {
    "segment_id": "opening",
    "interruptible": True,
    "keywords": ["欢迎"],
    "remaining_seconds": 100.0,
    "finished": False,
    "segment_text": "Hello!",
}


# --- classify_event ---

def test_classify_high_value_gift():
    e = Event(type="gift", user="X", gift="rocket", value=500, t=0)
    assert classify_event(e) == "P0"


def test_classify_low_value_gift():
    e = Event(type="gift", user="X", gift="heart", value=1, t=0)
    assert classify_event(e) == "P3"


def test_classify_follower_enter():
    e = Event(type="enter", user="Y", is_follower=True, t=0)
    assert classify_event(e) == "P1"


def test_classify_non_follower_enter():
    e = Event(type="enter", user="Y", is_follower=False, t=0)
    assert classify_event(e) == "P3"


def test_classify_question_danmaku():
    e = Event(type="danmaku", user="Z", text="这个怎么买？", t=0)
    assert classify_event(e) == "P2"


def test_classify_plain_danmaku():
    e = Event(type="danmaku", user="Z", text="主播加油！", t=0)
    assert classify_event(e) == "P3"


# --- Orchestrator rule layer ---

def test_p0_gift_triggers_immediate_tts():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert "VIP" in text
    assert speech_prompt is not None


def test_p1_follower_enter_triggers_tts():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    e = Event(type="enter", user="Fan", is_follower=True, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert "Fan" in text
    assert speech_prompt is not None


def test_p2_p3_go_to_buffer():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    for i in range(3):
        e = Event(type="danmaku", user=f"User{i}", text="加油！", t=float(i))
        orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert tts_q.empty()
    assert orch.buffer_size == 3


def test_get_events_clears_buffer():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    e = Event(type="danmaku", user="A", text="这个什么价格？", t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    events = orch.get_events()
    assert len(events) == 1
    assert orch.buffer_size == 0


def test_finished_state_blocks_all():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    finished = {**INTERRUPTIBLE_STATE, "finished": True}
    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, finished)

    assert tts_q.empty()
    assert orch.buffer_size == 0


# --- Strategy routing ---

import queue as _queue


def test_p0_intelligent_strategy_goes_to_urgent_queue():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue()
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "intelligent",
        urgent_queue=urgent_q,
    )
    event = Event(type="gift", user="Alice", gift="rocket", value=100, t=0)
    orch.handle_event(event, {"finished": False})
    assert urgent_q.qsize() == 1
    assert tts_q.qsize() == 0


def test_p0_immediate_strategy_goes_to_tts():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue()
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "immediate",
        urgent_queue=urgent_q,
    )
    event = Event(type="gift", user="Alice", gift="rocket", value=100, t=0)
    orch.handle_event(event, {"finished": False})
    assert tts_q.qsize() == 1
    assert urgent_q.qsize() == 0


def test_urgent_queue_full_drops_event():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue(maxsize=1)
    urgent_q.put("already_full")
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "intelligent",
        urgent_queue=urgent_q,
    )
    event = Event(type="gift", user="Bob", gift="rose", value=100, t=0)
    # Should not raise, just log warning
    orch.handle_event(event, {"finished": False})
    assert urgent_q.qsize() == 1  # still 1, not 2


def test_default_strategy_is_immediate():
    tts_q = _queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    event = Event(type="gift", user="Alice", gift="rocket", value=100, t=0)
    orch.handle_event(event, {"finished": False})
    assert tts_q.qsize() == 1
