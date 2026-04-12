"""Tests for Orchestrator P0/P1 rule interrupt layer."""
import queue

from scripts.live.orchestrator import Orchestrator, classify_event
from scripts.live.schema import Event

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
