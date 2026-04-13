"""Tests for DanmakuManager."""
from __future__ import annotations

import asyncio
import queue
import threading

import pytest

from src.live.danmaku_manager import DanmakuManager
from src.shared.event_bus import EventBus


def make_bus():
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    return EventBus(loop)


def test_initial_state_is_stopped():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    state = mgr.get_state()
    assert state["running"] is False


def test_start_sets_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    try:
        assert mgr.get_state()["running"] is True
    finally:
        mgr.stop()


def test_start_twice_raises():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    try:
        with pytest.raises(RuntimeError):
            mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    finally:
        mgr.stop()


def test_stop_sets_not_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    mgr.stop()
    assert mgr.get_state()["running"] is False


def test_stop_when_not_running_raises():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    with pytest.raises(RuntimeError):
        mgr.stop()


def test_get_orchestrator_returns_none_when_not_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    assert mgr.get_orchestrator() is None


def test_get_orchestrator_returns_orchestrator_when_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    try:
        assert mgr.get_orchestrator() is not None
    finally:
        mgr.stop()
