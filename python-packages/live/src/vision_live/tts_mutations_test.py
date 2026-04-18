"""Tests for the pure-function cross-container TTS mutations."""
from __future__ import annotations

import numpy as np

from vision_live.tts_mutations import UNSET, edit_by_id, remove_by_id, reorder_stage
from vision_live.tts_player import PcmItem, TtsItem
from vision_shared.ordered_item_store import OrderedItemStore


def _pcm(id_: str, text: str = "x", urgent: bool = False) -> PcmItem:
    return PcmItem(
        id=id_, text=text, speech_prompt=None,
        pcm=np.zeros(10, dtype=np.float32), duration=0.0,
        urgent=urgent,
    )


# ---- remove ----

def test_remove_finds_item_in_pending_stage():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    item = TtsItem.create("hi", None)
    in_q.put(item)

    result = remove_by_id(in_q, pcm_q, {}, item.id)
    assert result is not None
    stage, removed = result
    assert stage == "pending"
    assert removed.id == item.id
    assert in_q.qsize() == 0


def test_remove_finds_item_in_synthesized_stage():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    pcm = _pcm("abc")
    pcm_q.put(pcm)

    result = remove_by_id(in_q, pcm_q, {}, "abc")
    assert result is not None
    stage, removed = result
    assert stage == "synthesized"
    assert removed.id == "abc"
    assert pcm_q.qsize() == 0


def test_remove_sets_cancel_flag_when_item_in_flight():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    flying = TtsItem.create("flying", None)
    in_flight: dict[str, TtsItem] = {flying.id: flying}

    result = remove_by_id(in_q, pcm_q, in_flight, flying.id)
    assert result is not None
    stage, removed = result
    assert stage == "pending"
    assert removed.id == flying.id
    assert flying.cancel_flag is True


def test_remove_returns_none_when_id_missing_everywhere():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    assert remove_by_id(in_q, pcm_q, {}, "ghost") is None


# ---- edit ----

def test_edit_in_pending_stage_updates_text_in_place():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    item = TtsItem.create("old", "prompt-old", urgent=True)
    in_q.put(item)

    result = edit_by_id(in_q, pcm_q, item.id, "new", UNSET)
    assert result is not None
    stage, updated, old_id = result
    assert stage == "pending"
    assert updated.id == item.id
    assert updated.text == "new"
    assert updated.speech_prompt == "prompt-old"
    assert updated.urgent is True
    assert old_id is None


def test_edit_in_pending_stage_updates_prompt_when_provided():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    item = TtsItem.create("text", "old-prompt")
    in_q.put(item)

    result = edit_by_id(in_q, pcm_q, item.id, "text", "new-prompt")
    assert result is not None
    _, updated, _ = result
    assert updated.speech_prompt == "new-prompt"


def test_edit_in_synthesized_stage_discards_pcm_and_reenqueues_as_pending():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    pcm = _pcm("old-id", text="old", urgent=True)
    pcm_q.put(pcm)

    result = edit_by_id(in_q, pcm_q, "old-id", "new", UNSET)
    assert result is not None
    stage, new_item, old_id = result
    assert stage == "pending"
    assert old_id == "old-id"
    assert new_item.id != "old-id"
    assert new_item.text == "new"
    assert new_item.urgent is True
    assert pcm_q.qsize() == 0
    assert in_q.qsize() == 1
    assert in_q.snapshot()[0].id == new_item.id


def test_edit_returns_none_when_id_missing():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    assert edit_by_id(in_q, pcm_q, "missing", "x", UNSET) is None


# ---- reorder ----

def test_reorder_pending_matches_ids_list():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    items = [TtsItem.create(f"t{i}", None) for i in range(3)]
    for it in items:
        in_q.put(it)

    new_order = [items[2].id, items[0].id, items[1].id]
    assert reorder_stage(in_q, pcm_q, "pending", new_order) is True
    assert [it.id for it in in_q.snapshot()] == new_order


def test_reorder_synthesized_matches_ids_list():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    pcms = [_pcm(f"p{i}") for i in range(3)]
    for p in pcms:
        pcm_q.put(p)

    new_order = ["p2", "p0", "p1"]
    assert reorder_stage(in_q, pcm_q, "synthesized", new_order) is True
    assert [it.id for it in pcm_q.snapshot()] == new_order


def test_reorder_fails_when_ids_set_mismatches():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    a = TtsItem.create("a", None)
    b = TtsItem.create("b", None)
    in_q.put(a)
    in_q.put(b)

    assert reorder_stage(in_q, pcm_q, "pending", [a.id]) is False
    assert [it.id for it in in_q.snapshot()] == [a.id, b.id]


def test_reorder_fails_on_unknown_stage():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    assert reorder_stage(in_q, pcm_q, "playing", []) is False
