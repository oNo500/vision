"""Pure-function cross-container mutations on TTS queues.

Extracted from SessionManager so we can unit-test without the full
agent lifecycle. These functions do not publish SSE; callers do.
"""
from __future__ import annotations

from src.live.tts_player import PcmItem, TtsItem
from src.shared.ordered_item_store import OrderedItemStore


class _UnsetType:
    """Sentinel type for edit()'s speech_prompt to distinguish 'no change' from None."""
    __slots__ = ()


UNSET = _UnsetType()


def remove_by_id(
    in_queue: OrderedItemStore[TtsItem],
    pcm_queue: OrderedItemStore[PcmItem],
    in_flight: dict[str, TtsItem],
    item_id: str,
) -> tuple[str, TtsItem | PcmItem] | None:
    removed_pending = in_queue.remove(item_id)
    if removed_pending is not None:
        return ("pending", removed_pending)

    removed_synth = pcm_queue.remove(item_id)
    if removed_synth is not None:
        return ("synthesized", removed_synth)

    in_flight_item = in_flight.get(item_id)
    if in_flight_item is not None:
        in_flight_item.cancel_flag = True
        return ("pending", in_flight_item)

    return None


def edit_by_id(
    in_queue: OrderedItemStore[TtsItem],
    pcm_queue: OrderedItemStore[PcmItem],
    item_id: str,
    new_text: str,
    new_speech_prompt: str | None | _UnsetType,
) -> tuple[str, TtsItem, str | None] | None:
    def _mutator(old: TtsItem) -> TtsItem:
        return TtsItem(
            id=old.id,
            text=new_text,
            speech_prompt=old.speech_prompt if isinstance(new_speech_prompt, _UnsetType) else new_speech_prompt,
            stage=old.stage,
            urgent=old.urgent,
            cancel_flag=old.cancel_flag,
        )

    if in_queue.edit(item_id, _mutator):
        updated = next((it for it in in_queue.snapshot() if it.id == item_id), None)
        if updated is not None:
            return ("pending", updated, None)

    removed_pcm = pcm_queue.remove(item_id)
    if removed_pcm is not None:
        new_prompt = removed_pcm.speech_prompt if isinstance(new_speech_prompt, _UnsetType) else new_speech_prompt
        new_item = TtsItem.create(new_text, new_prompt, urgent=removed_pcm.urgent)
        in_queue.put(new_item)
        return ("pending", new_item, item_id)

    return None


def reorder_stage(
    in_queue: OrderedItemStore[TtsItem],
    pcm_queue: OrderedItemStore[PcmItem],
    stage: str,
    ids: list[str],
) -> bool:
    if stage == "pending":
        container: OrderedItemStore = in_queue
    elif stage == "synthesized":
        container = pcm_queue
    else:
        return False

    current_ids = [it.id for it in container.snapshot()]
    if set(current_ids) != set(ids) or len(current_ids) != len(ids):
        return False

    for target_index, item_id in enumerate(ids):
        container.move(item_id, target_index)
    return True
