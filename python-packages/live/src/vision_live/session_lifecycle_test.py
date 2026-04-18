"""Tests for SessionManager lifecycle + strategy management.

These hit only the state-machine surface — start/stop flow and strategy
get/set — without spinning up TTSPlayer/DirectorAgent, so they stay fast
and deterministic.
"""
from __future__ import annotations

import asyncio

import pytest

from vision_live.session import SessionAlreadyRunningError, SessionManager
from vision_shared.event_bus import EventBus


@pytest.fixture
def sm():
    loop = asyncio.new_event_loop()
    bus = EventBus(loop)
    yield SessionManager(bus)
    loop.close()


# ---------------------------------------------------------------------------
# initial state
# ---------------------------------------------------------------------------


def test_initial_state_not_running(sm: SessionManager):
    assert sm.get_state()["running"] is False


def test_initial_state_includes_strategy(sm: SessionManager):
    assert sm.get_state()["strategy"] == "immediate"


# ---------------------------------------------------------------------------
# strategy
# ---------------------------------------------------------------------------


def test_default_strategy_is_immediate(sm: SessionManager):
    assert sm.get_strategy() == "immediate"


def test_set_strategy_changes_value(sm: SessionManager):
    sm.set_strategy("intelligent")
    assert sm.get_strategy() == "intelligent"


def test_set_strategy_back_to_immediate(sm: SessionManager):
    sm.set_strategy("intelligent")
    sm.set_strategy("immediate")
    assert sm.get_strategy() == "immediate"


def test_set_invalid_strategy_raises(sm: SessionManager):
    with pytest.raises(ValueError):
        sm.set_strategy("banana")


# ---------------------------------------------------------------------------
# active plan
# ---------------------------------------------------------------------------


def test_active_plan_initially_none(sm: SessionManager):
    assert sm.get_active_plan() is None


def test_load_plan_sets_active_plan(sm: SessionManager):
    plan = {"id": "p1", "name": "demo", "product": {}, "persona": {}, "script": {"segments": []}}
    sm.load_plan(plan)
    assert sm.get_active_plan() == plan


# ---------------------------------------------------------------------------
# stop-when-not-running
# ---------------------------------------------------------------------------


def test_stop_when_not_running_raises(sm: SessionManager):
    with pytest.raises(RuntimeError):
        sm.stop()


# ---------------------------------------------------------------------------
# getters return None when not running
# ---------------------------------------------------------------------------


def test_get_tts_queue_none_when_not_running(sm: SessionManager):
    assert sm.get_tts_queue() is None


def test_get_urgent_queue_none_when_not_running(sm: SessionManager):
    assert sm.get_urgent_queue() is None


def test_get_script_runner_none_when_not_running(sm: SessionManager):
    assert sm.get_script_runner() is None


# ---------------------------------------------------------------------------
# start twice
# ---------------------------------------------------------------------------


def test_start_twice_raises(sm: SessionManager, monkeypatch: pytest.MonkeyPatch):
    """Stub _build_and_start so the state machine flips to running without
    actually spinning up ScriptRunner / TTSPlayer."""
    monkeypatch.setattr(sm, "_build_and_start", lambda *a, **kw: None)
    sm.start(script_path="x", product_path="y", mock=True, project=None)

    with pytest.raises(SessionAlreadyRunningError):
        sm.start(script_path="x", product_path="y", mock=True, project=None)


def test_start_failure_resets_running_flag(sm: SessionManager, monkeypatch: pytest.MonkeyPatch):
    def boom(*_a, **_kw):
        raise RuntimeError("build failed")

    monkeypatch.setattr(sm, "_build_and_start", boom)

    with pytest.raises(RuntimeError):
        sm.start(script_path="x", product_path="y", mock=True, project=None)

    assert sm.get_state()["running"] is False
