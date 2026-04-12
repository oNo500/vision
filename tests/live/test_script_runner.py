"""Tests for ScriptRunner segment advance logic."""
import time

from src.live.schema import LiveScript
from src.live.script_runner import ScriptRunner

SAMPLE_DATA = {
    "meta": {"title": "Test", "total_duration": 300},
    "segments": [
        {"id": "opening", "duration": 2, "text": "Hello!", "interruptible": True},
        {"id": "core", "duration": 2, "text": "Core content.", "interruptible": False},
        {"id": "closing", "duration": 2, "text": "Goodbye!", "interruptible": True},
    ],
}


def test_initial_state():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    state = runner.get_state()
    assert state["segment_id"] == "opening"
    assert state["interruptible"] is True
    assert state["finished"] is False


def test_advance_to_next_segment():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    time.sleep(2.5)   # opening duration = 2s
    state = runner.get_state()
    runner.stop()
    assert state["segment_id"] == "core"
    assert state["interruptible"] is False


def test_finished_after_all_segments():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    time.sleep(7)   # 3 segments × 2s + buffer
    state = runner.get_state()
    runner.stop()
    assert state["finished"] is True


def test_remaining_seconds_decreases():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    time.sleep(0.5)
    state = runner.get_state()
    runner.stop()
    assert state["remaining_seconds"] < 2


def test_stop_is_idempotent():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    runner.stop()
    runner.stop()   # should not raise


def test_advance_skips_to_next_segment():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.advance()
    state = runner.get_state()
    assert state["segment_id"] == "core"
    assert state["remaining_seconds"] > 0


def test_advance_at_last_segment_does_nothing():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.advance()  # opening → core
    runner.advance()  # core → closing
    runner.advance()  # closing → no-op (last)
    state = runner.get_state()
    assert state["segment_id"] == "closing"


def test_rewind_goes_to_previous_segment():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.advance()  # → core
    runner.rewind()   # → opening
    state = runner.get_state()
    assert state["segment_id"] == "opening"


def test_rewind_at_first_segment_does_nothing():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.rewind()  # no-op
    state = runner.get_state()
    assert state["segment_id"] == "opening"
