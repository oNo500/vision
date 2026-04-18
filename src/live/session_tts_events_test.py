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


def test_tts_queue_snapshot_includes_stage_and_urgent():
    """SessionManager.get_tts_queue_snapshot() returns stage + urgent per item."""
    from src.live.session import SessionManager

    # Stub the internal queue + player with simple .snapshot() containers.
    # We are not testing start/stop lifecycle, only the snapshot shape transformation.
    pending = TtsItem.create("pending one", None, urgent=True)
    synthesized = PcmItem(
        id="s1",
        text="synthesized one",
        speech_prompt=None,
        pcm=np.zeros(10, dtype=np.float32),
        duration=0.0,
        urgent=False,
    )

    class _StubStore:
        def __init__(self, items):
            self._items = items
        def snapshot(self):
            return list(self._items)

    class _StubPlayer:
        def __init__(self, items):
            self._pcm_queue = _StubStore(items)

    # SessionManager needs a real-enough bus for __init__. Use None-compatible stub.
    class _NopBus:
        def publish(self, _event): pass

    mgr = SessionManager(_NopBus())
    mgr._running = True
    mgr._tts_queue = _StubStore([pending])
    mgr._tts_player = _StubPlayer([synthesized])

    snap = mgr.get_tts_queue_snapshot()

    assert len(snap) == 2
    p, s = snap
    assert p["id"] == pending.id
    assert p["stage"] == "pending"
    assert p["urgent"] is True
    assert s["id"] == "s1"
    assert s["stage"] == "synthesized"
    assert s["urgent"] is False
