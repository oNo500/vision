"""Tests for ScriptRunner segment-advance logic."""
from __future__ import annotations

import time

from src.live.schema import LiveScript, ScriptSegment
from src.live.script_runner import ScriptRunner


def _script(*durations: int) -> LiveScript:
    return LiveScript(
        title="Test",
        total_duration=sum(durations),
        segments=[
            ScriptSegment(
                id=f"s{i}",
                title=f"段落{i + 1}",
                goal=f"do step {i}",
                duration=d,
                cue=[],
                must_say=False,
                keywords=[],
            )
            for i, d in enumerate(durations)
        ],
    )


def test_initial_state_points_at_first_segment():
    runner = ScriptRunner(_script(2, 2))
    state = runner.get_state()
    assert state["segment_id"] == "s0"
    assert state["title"] == "段落1"
    assert state["finished"] is False


def test_advance_moves_to_next_segment():
    runner = ScriptRunner(_script(60, 60))
    runner.advance()
    assert runner.get_state()["segment_id"] == "s1"


def test_advance_at_last_segment_is_noop():
    runner = ScriptRunner(_script(60, 60, 60))
    runner.advance()   # s0 → s1
    runner.advance()   # s1 → s2 (last)
    runner.advance()   # no-op
    assert runner.get_state()["segment_id"] == "s2"


def test_rewind_moves_to_previous_segment():
    runner = ScriptRunner(_script(60, 60))
    runner.advance()
    runner.rewind()
    assert runner.get_state()["segment_id"] == "s0"


def test_rewind_at_first_segment_is_noop():
    runner = ScriptRunner(_script(60, 60))
    runner.rewind()
    assert runner.get_state()["segment_id"] == "s0"


def test_timer_advances_segment_automatically():
    runner = ScriptRunner(_script(1, 1))
    runner.start()
    time.sleep(1.3)
    state = runner.get_state()
    runner.stop()
    assert state["segment_id"] == "s1"


def test_finished_state_after_all_segments_elapsed():
    runner = ScriptRunner(_script(1, 1))
    runner.start()
    time.sleep(2.5)
    state = runner.get_state()
    runner.stop()
    assert state["finished"] is True


def test_remaining_seconds_decreases_over_time():
    runner = ScriptRunner(_script(5))
    runner.start()
    time.sleep(0.3)
    state = runner.get_state()
    runner.stop()
    assert 4.0 < state["remaining_seconds"] < 5.0


def test_stop_is_idempotent():
    runner = ScriptRunner(_script(60))
    runner.start()
    runner.stop()
    runner.stop()   # must not raise
