"""Tests for SessionManager — Agent lifecycle and EventBus wiring."""
import asyncio
import queue
import time
import pytest
from unittest.mock import MagicMock, patch
from src.live.session import SessionManager
from src.shared.event_bus import EventBus


@pytest.fixture
def loop():
    lp = asyncio.new_event_loop()
    yield lp
    lp.close()


@pytest.fixture
def bus(loop):
    return EventBus(loop)


@pytest.fixture
def manager(bus):
    return SessionManager(bus)


def test_initial_state_is_stopped(manager):
    state = manager.get_state()
    assert state["running"] is False


def _patch_session_start(manager, **kwargs):
    """Helper to start manager with all components mocked."""
    with patch("src.live.session.ScriptRunner") as MockSR, \
         patch("src.live.session.KnowledgeBase") as MockKB, \
         patch("src.live.session.TTSPlayer") as MockTTS, \
         patch("src.live.session.DirectorAgent") as MockDA:
        for Mock in [MockSR, MockTTS, MockDA]:
            Mock.return_value.start = MagicMock()
            Mock.return_value.stop = MagicMock()
        MockSR.from_yaml.return_value = MockSR.return_value
        MockKB.return_value.context_for_prompt.return_value = "ctx"
        MockKB.return_value.product_name = "Test"
        MockDA.return_value.start = MagicMock()
        manager.start(
            script_path="src/live/example_script.yaml",
            product_path="src/live/data/product.yaml",
            mock=True,
            project=None,
            **kwargs,
        )


def test_start_sets_running(manager):
    with patch("src.live.session.ScriptRunner") as MockSR, \
         patch("src.live.session.KnowledgeBase") as MockKB, \
         patch("src.live.session.TTSPlayer") as MockTTS, \
         patch("src.live.session.DirectorAgent") as MockDA:
        for Mock in [MockSR, MockTTS, MockDA]:
            Mock.return_value.start = MagicMock()
            Mock.return_value.stop = MagicMock()
        MockSR.from_yaml.return_value = MockSR.return_value
        MockKB.return_value.context_for_prompt.return_value = "ctx"
        MockKB.return_value.product_name = "Test"
        MockDA.return_value.start = MagicMock()

        manager.start(
            script_path="src/live/example_script.yaml",
            product_path="src/live/data/product.yaml",
            mock=True,
            project=None,
        )
        assert manager.get_state()["running"] is True
        manager.stop()


def test_start_twice_raises(manager):
    with patch("src.live.session.ScriptRunner") as MockSR, \
         patch("src.live.session.KnowledgeBase") as MockKB, \
         patch("src.live.session.TTSPlayer") as MockTTS, \
         patch("src.live.session.DirectorAgent") as MockDA:
        for Mock in [MockSR, MockTTS, MockDA]:
            Mock.return_value.start = MagicMock()
            Mock.return_value.stop = MagicMock()
        MockSR.from_yaml.return_value = MockSR.return_value
        MockKB.return_value.context_for_prompt.return_value = "ctx"
        MockKB.return_value.product_name = "Test"
        MockDA.return_value.start = MagicMock()

        manager.start("src/live/example_script.yaml", "src/live/data/product.yaml", True, None)
        with pytest.raises(RuntimeError, match="already running"):
            manager.start("src/live/example_script.yaml", "src/live/data/product.yaml", True, None)
        manager.stop()


def test_stop_when_not_running_raises(manager):
    with pytest.raises(RuntimeError, match="not running"):
        manager.stop()


def test_stop_sets_not_running(manager):
    with patch("src.live.session.ScriptRunner") as MockSR, \
         patch("src.live.session.KnowledgeBase") as MockKB, \
         patch("src.live.session.TTSPlayer") as MockTTS, \
         patch("src.live.session.DirectorAgent") as MockDA:
        for Mock in [MockSR, MockTTS, MockDA]:
            Mock.return_value.start = MagicMock()
            Mock.return_value.stop = MagicMock()
        MockSR.from_yaml.return_value = MockSR.return_value
        MockKB.return_value.context_for_prompt.return_value = "ctx"
        MockKB.return_value.product_name = "Test"
        MockDA.return_value.start = MagicMock()

        manager.start("src/live/example_script.yaml", "src/live/data/product.yaml", True, None)
        manager.stop()
        assert manager.get_state()["running"] is False


def test_inject_when_not_running_raises(manager):
    with pytest.raises(RuntimeError, match="not running"):
        manager.inject("hello", None)


def test_default_strategy_is_immediate(manager):
    assert manager.get_strategy() == "immediate"


def test_set_strategy_changes_value(manager):
    manager.set_strategy("intelligent")
    assert manager.get_strategy() == "intelligent"


def test_set_invalid_strategy_raises(manager):
    with pytest.raises(ValueError):
        manager.set_strategy("unknown")


def test_get_state_includes_strategy(manager):
    state = manager.get_state()
    assert "strategy" in state


def test_urgent_queue_none_when_not_running(manager):
    assert manager.get_urgent_queue() is None
