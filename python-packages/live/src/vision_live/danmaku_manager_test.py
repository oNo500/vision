"""Tests for DanmakuManager lifecycle."""
from __future__ import annotations

import asyncio

import pytest

from vision_live.danmaku_manager import DanmakuManager
from vision_shared.event_bus import EventBus


@pytest.fixture
def dm():
    loop = asyncio.new_event_loop()
    bus = EventBus(loop)
    mgr = DanmakuManager(bus)
    yield mgr
    if mgr.get_state()["running"]:
        mgr.stop()
    loop.close()


def test_initial_state_not_running(dm: DanmakuManager):
    state = dm.get_state()
    assert state["running"] is False
    assert state["buffer_size"] == 0


def test_get_orchestrator_none_when_not_running(dm: DanmakuManager):
    assert dm.get_orchestrator() is None


def test_stop_when_not_running_raises(dm: DanmakuManager):
    with pytest.raises(RuntimeError):
        dm.stop()


def test_start_mock_gets_orchestrator(dm: DanmakuManager):
    dm.start(
        mock=True,
        cdp_url=None,
        tts_queue=None,
        get_strategy_fn=lambda: "immediate",
        urgent_queue=None,
    )
    assert dm.get_state()["running"] is True
    assert dm.get_orchestrator() is not None


def test_start_twice_raises(dm: DanmakuManager):
    dm.start(
        mock=True, cdp_url=None, tts_queue=None,
        get_strategy_fn=lambda: "immediate", urgent_queue=None,
    )
    with pytest.raises(RuntimeError):
        dm.start(
            mock=True, cdp_url=None, tts_queue=None,
            get_strategy_fn=lambda: "immediate", urgent_queue=None,
        )


def test_stop_clears_orchestrator(dm: DanmakuManager):
    dm.start(
        mock=True, cdp_url=None, tts_queue=None,
        get_strategy_fn=lambda: "immediate", urgent_queue=None,
    )
    dm.stop()
    assert dm.get_state()["running"] is False
    assert dm.get_orchestrator() is None
