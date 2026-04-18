"""Tests for SSE events SessionManager publishes when TTS items flow."""
from __future__ import annotations

import numpy as np
import pytest

from src.live.tts_player import PcmItem, TtsItem


@pytest.fixture
def bus_with_collector():
    """Stub bus: captures every event passed to publish()."""
    collected: list[dict] = []

    class _Bus:
        def publish(self, event: dict) -> None:
            collected.append(event)

    return _Bus(), collected


def test_tts_queued_payload_includes_stage_and_urgent(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_queued

    item = TtsItem.create("hi", None, urgent=True)
    _publish_tts_queued(bus, item)

    assert len(collected) == 1
    ev = collected[0]
    assert ev["type"] == "tts_queued"
    assert ev["id"] == item.id
    assert ev["content"] == "hi"
    assert ev["stage"] == "pending"
    assert ev["urgent"] is True
    assert "ts" in ev


def test_tts_synthesized_event_has_id_and_stage(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_synthesized

    pcm = PcmItem(
        id="abc",
        text="x",
        speech_prompt=None,
        pcm=np.zeros(10, dtype=np.float32),
        duration=0.1,
        urgent=False,
    )
    _publish_tts_synthesized(bus, pcm)

    assert len(collected) == 1
    ev = collected[0]
    assert ev["type"] == "tts_synthesized"
    assert ev["id"] == "abc"
    assert ev["stage"] == "synthesized"
