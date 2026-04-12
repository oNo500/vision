"""Tests for TTSPlayer async queue consumer."""
import queue
import time

from scripts.live.tts_player import TTSPlayer


def test_player_consumes_items():
    q: queue.Queue[str] = queue.Queue()
    spoken = []

    def mock_speak(text: str) -> None:
        spoken.append(text)
        time.sleep(0.05)   # simulate short speak time

    player = TTSPlayer(q, speak_fn=mock_speak)
    player.start()
    q.put("Hello world")
    q.put("How are you")
    time.sleep(0.5)
    player.stop()
    assert spoken == ["Hello world", "How are you"]


def test_is_speaking_flag():
    q: queue.Queue[str] = queue.Queue()

    def slow_speak(text: str) -> None:
        time.sleep(0.2)

    player = TTSPlayer(q, speak_fn=slow_speak)
    player.start()
    q.put("Something long")
    time.sleep(0.05)
    assert player.is_speaking is True
    time.sleep(0.3)
    assert player.is_speaking is False
    player.stop()


def test_stop_is_idempotent():
    q: queue.Queue[str] = queue.Queue()
    player = TTSPlayer(q, speak_fn=lambda t: None)
    player.start()
    player.stop()
    player.stop()   # should not raise
