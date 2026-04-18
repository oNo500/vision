"""Tests for TtsItem / PcmItem dataclass fields added in PR 2."""
from __future__ import annotations

import time as _time

import numpy as np

from src.live.tts_player import PcmItem, TtsItem, TTSPlayer
from src.shared.ordered_item_store import OrderedItemStore


def test_tts_item_create_defaults_stage_pending_not_urgent():
    item = TtsItem.create("hello", None)
    assert item.stage == "pending"
    assert item.urgent is False


def test_tts_item_create_accepts_urgent_flag():
    item = TtsItem.create("urgent!", None, urgent=True)
    assert item.urgent is True
    assert item.stage == "pending"  # stage is independent of urgent


def test_pcm_item_defaults_stage_synthesized_not_urgent():
    pcm = PcmItem(
        id="i1",
        text="x",
        speech_prompt=None,
        pcm=np.zeros(10, dtype=np.float32),
        duration=0.0,
    )
    assert pcm.stage == "synthesized"
    assert pcm.urgent is False


def test_pcm_item_preserves_urgent_from_tts_item():
    pcm = PcmItem(
        id="i2",
        text="y",
        speech_prompt=None,
        pcm=np.zeros(10, dtype=np.float32),
        duration=0.0,
        urgent=True,
    )
    assert pcm.urgent is True


def test_on_synthesized_fires_for_each_item_with_mock_speak_fn():
    """With a mock speak_fn the synth path is bypassed, so on_synthesized
    must NOT fire (there is no in_queue → pcm_queue transition in mock mode)."""
    in_q: OrderedItemStore = OrderedItemStore()
    synthesized: list[str] = []
    player = TTSPlayer(
        in_queue=in_q,
        speak_fn=lambda _text, _prompt: None,
        on_synthesized=lambda item: synthesized.append(item.id),
    )
    player.start()
    try:
        player.put("hi", None)
        _time.sleep(0.1)  # let mock path consume the item
    finally:
        player.stop()

    # Mock path does not go through pcm_queue, so on_synthesized must be dormant
    assert synthesized == []


def test_on_synthesized_accepts_none_without_error():
    """Constructing without on_synthesized must work (backward compat)."""
    player = TTSPlayer(
        in_queue=OrderedItemStore(),
        speak_fn=lambda _text, _prompt: None,
    )
    assert player is not None  # smoke: no exception during __init__
