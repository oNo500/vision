"""Tests for TTSPlayer runtime behaviour (mock speak path)."""
from __future__ import annotations

import time

from src.live.tts_player import TTSPlayer, TtsItem
from vision_shared.ordered_item_store import OrderedItemStore


def test_player_consumes_items_in_order():
    q = OrderedItemStore(maxsize=10)
    spoken: list[tuple[str, str | None]] = []

    def mock_speak(text: str, speech_prompt: str | None = None) -> None:
        spoken.append((text, speech_prompt))
        time.sleep(0.02)

    player = TTSPlayer(q, speak_fn=mock_speak)
    player.start()
    q.put(TtsItem.create("Hello world", None))
    q.put(TtsItem.create("How are you", "快速热情"))
    time.sleep(0.3)
    player.stop()

    assert spoken == [("Hello world", None), ("How are you", "快速热情")]


def test_is_speaking_flag_true_while_speaking_false_after():
    q = OrderedItemStore(maxsize=10)

    def slow_speak(_text: str, _prompt: str | None = None) -> None:
        time.sleep(0.2)

    player = TTSPlayer(q, speak_fn=slow_speak)
    player.start()
    q.put(TtsItem.create("Something long", None))
    time.sleep(0.05)
    assert player.is_speaking is True
    time.sleep(0.3)
    assert player.is_speaking is False
    player.stop()


def test_stop_is_idempotent():
    q = OrderedItemStore(maxsize=10)
    player = TTSPlayer(q, speak_fn=lambda _t, _p=None: None)
    player.start()
    player.stop()
    player.stop()   # must not raise


def test_put_returns_tts_item_with_id():
    q = OrderedItemStore(maxsize=10)
    player = TTSPlayer(q, speak_fn=lambda _t, _p=None: None)
    item = player.put("hi", "自然", urgent=False)
    assert isinstance(item, TtsItem)
    assert item.id
    assert item.text == "hi"
    assert item.speech_prompt == "自然"


def test_on_queued_callback_fires_for_each_put():
    q = OrderedItemStore(maxsize=10)
    seen: list[TtsItem] = []
    player = TTSPlayer(
        q,
        speak_fn=lambda _t, _p=None: None,
        on_queued=seen.append,
    )
    player.put("a", None)
    player.put("b", None)
    assert [i.text for i in seen] == ["a", "b"]


def test_on_play_callback_fires_before_speak():
    q = OrderedItemStore(maxsize=10)
    played: list[str] = []

    player = TTSPlayer(
        q,
        speak_fn=lambda text, _p=None: played.append(f"spoke:{text}"),
        on_play=lambda item: played.append(f"play:{item.text}"),
    )
    player.start()
    q.put(TtsItem.create("X", None))
    time.sleep(0.15)
    player.stop()

    assert played == ["play:X", "spoke:X"]


def test_on_done_callback_fires_after_speak():
    q = OrderedItemStore(maxsize=10)
    order: list[str] = []

    player = TTSPlayer(
        q,
        speak_fn=lambda text, _p=None: order.append(f"spoke:{text}"),
        on_done=lambda item: order.append(f"done:{item.text}"),
    )
    player.start()
    q.put(TtsItem.create("Y", None))
    time.sleep(0.15)
    player.stop()

    assert order == ["spoke:Y", "done:Y"]
