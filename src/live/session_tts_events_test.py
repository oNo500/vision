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


def test_publish_tts_removed(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_removed

    _publish_tts_removed(bus, "abc", "pending")

    assert len(collected) == 1
    ev = collected[0]
    assert ev["type"] == "tts_removed"
    assert ev["id"] == "abc"
    assert ev["stage"] == "pending"
    assert "ts" in ev


def test_publish_tts_edited_in_place(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_edited

    edited = TtsItem.create("rewritten", "prompt-b", urgent=False)
    _publish_tts_edited(bus, edited, old_id=None, stage="pending")

    ev = collected[0]
    assert ev["type"] == "tts_edited"
    assert ev["id"] == edited.id
    assert ev["new_id"] == edited.id  # in-place: id == new_id
    assert ev["content"] == "rewritten"
    assert ev["speech_prompt"] == "prompt-b"
    assert ev["stage"] == "pending"


def test_publish_tts_edited_with_id_swap(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_edited

    new_item = TtsItem.create("rewritten", None, urgent=True)
    _publish_tts_edited(bus, new_item, old_id="old-xyz", stage="pending")

    ev = collected[0]
    assert ev["id"] == "old-xyz"
    assert ev["new_id"] == new_item.id
    assert ev["stage"] == "pending"


def test_publish_tts_reordered(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_reordered

    _publish_tts_reordered(bus, "pending", ["b", "a", "c"])

    ev = collected[0]
    assert ev["type"] == "tts_reordered"
    assert ev["stage"] == "pending"
    assert ev["ids"] == ["b", "a", "c"]
    assert "ts" in ev


# ---- SessionManager integration tests ----

def test_session_remove_tts_finds_pending_and_publishes():
    from src.live.session import SessionManager
    from src.shared.ordered_item_store import OrderedItemStore

    class _StubBus:
        def __init__(self): self.events: list[dict] = []
        def publish(self, ev): self.events.append(ev)

    bus = _StubBus()
    mgr = SessionManager(bus)
    mgr._running = True

    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    item = TtsItem.create("hi", None)
    in_q.put(item)

    class _StubPlayer:
        def __init__(self, pcm_q): self._pcm_queue = pcm_q
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = in_q
    mgr._tts_player = _StubPlayer(pcm_q)

    ok = mgr.remove_tts(item.id)
    assert ok is True
    assert in_q.qsize() == 0
    assert any(e["type"] == "tts_removed" and e["id"] == item.id for e in bus.events)


def test_session_remove_tts_returns_false_when_id_missing():
    from src.live.session import SessionManager
    from src.shared.ordered_item_store import OrderedItemStore

    class _StubBus:
        def publish(self, _ev): pass

    mgr = SessionManager(_StubBus())
    mgr._running = True

    class _StubPlayer:
        def __init__(self): self._pcm_queue = OrderedItemStore()
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = OrderedItemStore()
    mgr._tts_player = _StubPlayer()

    assert mgr.remove_tts("ghost") is False


def test_session_remove_tts_returns_false_when_not_running():
    from src.live.session import SessionManager
    class _StubBus:
        def publish(self, _ev): pass
    mgr = SessionManager(_StubBus())
    # _running default is False
    assert mgr.remove_tts("any") is False


def test_session_edit_tts_pending_updates_in_place():
    from src.live.session import SessionManager
    from src.live.tts_mutations import UNSET
    from src.shared.ordered_item_store import OrderedItemStore

    class _StubBus:
        def __init__(self): self.events: list[dict] = []
        def publish(self, ev): self.events.append(ev)

    bus = _StubBus()
    mgr = SessionManager(bus)
    mgr._running = True

    in_q: OrderedItemStore = OrderedItemStore()
    item = TtsItem.create("old", None)
    in_q.put(item)

    class _StubPlayer:
        def __init__(self): self._pcm_queue = OrderedItemStore()
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = in_q
    mgr._tts_player = _StubPlayer()

    ok = mgr.edit_tts(item.id, "new", UNSET)
    assert ok is True
    assert in_q.snapshot()[0].text == "new"
    assert any(e["type"] == "tts_edited" and e["id"] == item.id for e in bus.events)


def test_session_edit_tts_returns_false_when_id_missing():
    from src.live.session import SessionManager
    from src.live.tts_mutations import UNSET
    from src.shared.ordered_item_store import OrderedItemStore

    class _StubBus:
        def publish(self, _ev): pass

    mgr = SessionManager(_StubBus())
    mgr._running = True

    class _StubPlayer:
        def __init__(self): self._pcm_queue = OrderedItemStore()
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = OrderedItemStore()
    mgr._tts_player = _StubPlayer()

    assert mgr.edit_tts("ghost", "new", UNSET) is False


def test_session_reorder_tts_valid_ids():
    from src.live.session import SessionManager
    from src.shared.ordered_item_store import OrderedItemStore

    class _StubBus:
        def __init__(self): self.events: list[dict] = []
        def publish(self, ev): self.events.append(ev)

    bus = _StubBus()
    mgr = SessionManager(bus)
    mgr._running = True

    in_q: OrderedItemStore = OrderedItemStore()
    items = [TtsItem.create(f"t{i}", None) for i in range(3)]
    for it in items:
        in_q.put(it)

    class _StubPlayer:
        def __init__(self): self._pcm_queue = OrderedItemStore()
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = in_q
    mgr._tts_player = _StubPlayer()

    new_order = [items[2].id, items[0].id, items[1].id]
    ok = mgr.reorder_tts("pending", new_order)
    assert ok is True
    assert [it.id for it in in_q.snapshot()] == new_order
    assert any(e["type"] == "tts_reordered" for e in bus.events)


def test_session_reorder_tts_returns_false_on_mismatched_ids():
    from src.live.session import SessionManager
    from src.shared.ordered_item_store import OrderedItemStore

    class _StubBus:
        def publish(self, _ev): pass

    mgr = SessionManager(_StubBus())
    mgr._running = True

    in_q: OrderedItemStore = OrderedItemStore()
    in_q.put(TtsItem.create("a", None))

    class _StubPlayer:
        def __init__(self): self._pcm_queue = OrderedItemStore()
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = in_q
    mgr._tts_player = _StubPlayer()

    assert mgr.reorder_tts("pending", ["wrong-id"]) is False
