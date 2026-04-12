"""Tests for Orchestrator two-layer decision engine."""
import queue
from unittest.mock import MagicMock

from scripts.live.orchestrator import Orchestrator, classify_event
from scripts.live.schema import Decision, Event

INTERRUPTIBLE_STATE = {
    "segment_id": "opening",
    "interruptible": True,
    "keywords": ["欢迎"],
    "remaining_seconds": 100.0,
    "finished": False,
    "segment_text": "Hello!",
}

NOT_INTERRUPTIBLE_STATE = {
    **INTERRUPTIBLE_STATE,
    "interruptible": False,
    "segment_id": "product_core",
}


# --- classify_event tests ---

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


# --- Orchestrator rule layer tests ---

def test_p0_gift_triggers_immediate_tts():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_llm = MagicMock()
    orch = Orchestrator(tts_queue=tts_q, llm_client=mock_llm, llm_batch_size=5, llm_interval=10.0)

    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert "VIP" in text
    assert speech_prompt is not None
    mock_llm.decide.assert_not_called()


def test_p1_follower_enter_triggers_tts():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q, llm_client=MagicMock(), llm_batch_size=5, llm_interval=10.0)

    e = Event(type="enter", user="Fan", is_follower=True, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert "Fan" in text
    assert speech_prompt is not None


def test_not_interruptible_blocks_all_events():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_llm = MagicMock()
    orch = Orchestrator(tts_queue=tts_q, llm_client=mock_llm, llm_batch_size=5, llm_interval=10.0)

    # Even P0 gift should not emit TTS when segment is not interruptible
    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, NOT_INTERRUPTIBLE_STATE)

    assert tts_q.empty()
    mock_llm.decide.assert_not_called()


def test_p3_events_accumulate_in_buffer():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q, llm_client=MagicMock(), llm_batch_size=5, llm_interval=10.0)

    for i in range(3):
        e = Event(type="danmaku", user=f"User{i}", text="加油！", t=float(i))
        orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert tts_q.empty()   # not enough to trigger LLM yet
    assert orch.buffer_size == 3


def test_llm_triggered_at_batch_size():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_llm = MagicMock()
    mock_llm.decide.return_value = Decision(action="respond", content="感谢大家！", reason="test")
    orch = Orchestrator(tts_queue=tts_q, llm_client=mock_llm, llm_batch_size=3, llm_interval=10.0)

    for i in range(3):
        e = Event(type="danmaku", user=f"User{i}", text="加油！", t=float(i))
        orch.handle_event(e, INTERRUPTIBLE_STATE)

    mock_llm.decide.assert_called_once()
    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert text == "感谢大家！"
    assert speech_prompt is None   # no speech_prompt in mock Decision
