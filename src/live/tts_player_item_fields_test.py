"""Tests for TtsItem / PcmItem dataclass fields added in PR 2."""
from __future__ import annotations

import numpy as np

from src.live.tts_player import PcmItem, TtsItem


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
