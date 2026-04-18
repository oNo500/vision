# PR 3: Mutation Endpoints + BroadcastPipeline UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose three mutation REST endpoints (`DELETE` / `PATCH` / `POST reorder`) for pending + synthesized TTS items, publish three corresponding SSE events (`tts_removed` / `tts_edited` / `tts_reordered`), and replace the `AiStatusCard` + `TtsQueuePanel` + `AiOutputLog` trio with a single `BroadcastPipeline` component that mirrors the lifecycle pending → synthesized → playing → done using in-stage drag-and-drop and `motion` layoutId cross-stage animations.

**Architecture:** Backend gets three new `SessionManager` methods that compose `OrderedItemStore` mutators with cross-container logic (editing a synthesized item discards the PCM and re-enqueues at the pending tail). Frontend centralizes pipeline rendering in one component tree; existing three components are deleted after the new one is wired into `live/page.tsx`.

**Tech Stack:** Python 3.13 + FastAPI + pytest + httpx TestClient; React 19 + `@atlaskit/pragmatic-drag-and-drop` (already installed) + `motion` (already in @workspace/ui) + vitest.

---

## Design decisions locked in from brainstorming

| # | Decision | Consequence |
|---|---|---|
| 1 | Edit purpose: full rewrite | Multi-line textarea + char count |
| 2 | Synthesized stage supports add/del/edit/reorder | Edit discards PCM, re-enqueues at pending tail |
| 3 | Drag: in-stage only | Two `SortableContext`-equivalent zones |
| 4 | Urgent display | Red-dot badge on the item (no separate section) |

---

## File Map

**Backend create:**
- `src/live/tts_mutations.py` — pure-function cross-container helpers (extracted from SessionManager for testability)
- `src/live/tts_mutations_test.py` — unit tests for the helpers

**Backend modify:**
- `src/live/session.py` — `remove_tts`, `edit_tts`, `reorder_tts` methods that call into helpers + publish SSE; `_on_queued` closure also gains an `_in_flight` registry for cancel-safe remove of items currently being synthesized
- `src/live/tts_player.py` — `_run_synth` checks a `cancel_flag` on the item after Google TTS returns; if set, discards the PCM instead of pushing into `pcm_queue`
- `src/live/routes.py` — 3 new endpoints: `DELETE`, `PATCH`, `POST reorder`
- `src/live/routes_test.py` — 6 new endpoint tests covering 200 / 400 / 404 paths

**Frontend create:**
- `apps/web/src/features/live/components/broadcast-pipeline/index.tsx` — top-level layout + layout animation host
- `apps/web/src/features/live/components/broadcast-pipeline/pipeline-header.tsx` — LLM status + aggregate counts
- `apps/web/src/features/live/components/broadcast-pipeline/stage-section.tsx` — reusable region with drop-target for one stage
- `apps/web/src/features/live/components/broadcast-pipeline/pipeline-item.tsx` — individual card with hover-triggered edit/delete buttons + urgent badge + `motion.div layoutId`
- `apps/web/src/features/live/components/broadcast-pipeline/pipeline-item-editor.tsx` — multi-line textarea dialog for edit
- `apps/web/src/features/live/components/broadcast-pipeline/now-playing-card.tsx` — full-width card for the playing stage
- `apps/web/src/features/live/components/broadcast-pipeline/history-section.tsx` — collapsible "done" history drawer
- `apps/web/src/features/live/hooks/use-tts-mutations.ts` — encapsulates the three REST calls with optimistic updates + rollback on 4xx
- `apps/web/src/features/live/hooks/use-tts-mutations.test.ts`
- vitest suites for 3 new components (`broadcast-pipeline.test.tsx`, `pipeline-item.test.tsx`, `stage-section.test.tsx`)

**Frontend modify:**
- `apps/web/src/app/(dashboard)/live/page.tsx` — delete the 3-component center column and render `<BroadcastPipeline>` instead
- `apps/web/src/app/(dashboard)/live/page.test.tsx` — replace component mocks accordingly
- `apps/web/src/features/live/hooks/use-live-stream.ts` — handle 3 new event types (`tts_removed` / `tts_edited` / `tts_reordered`) in `applyLiveEvent`
- `apps/web/src/features/live/hooks/use-live-stream.test.ts` — add 3 new reducer tests

**Frontend delete (after new component wired):**
- `apps/web/src/features/live/components/ai-status-card.tsx` (+ any test)
- `apps/web/src/features/live/components/tts-queue-panel.tsx` (+ any test)
- `apps/web/src/features/live/components/ai-output-log.tsx` (+ any test)

---

## Task 1: Extract cross-container mutation helpers

**Files:**
- Create: `src/live/tts_mutations.py`
- Create: `src/live/tts_mutations_test.py`

### Context

The three mutation operations (remove / edit / reorder) each touch either `in_queue` or `pcm_queue` depending on stage. For edit of a synthesized item, both containers are touched atomically. Extracting these as pure functions makes them unit-testable without spinning up a SessionManager + TTSPlayer + threads.

Signatures:

```python
def remove_by_id(
    in_queue: OrderedItemStore[TtsItem],
    pcm_queue: OrderedItemStore[PcmItem],
    in_flight: dict[str, TtsItem],  # items currently being synthesized
    item_id: str,
) -> tuple[str, TtsItem | PcmItem] | None:
    """Remove from whichever container holds it. Returns (stage, removed_item) or None.

    When the item is in `in_flight` (between `in_queue.get()` and `pcm_queue.put()`),
    mutate the item to set cancel_flag=True so _run_synth discards it. Returns
    ("pending", item) in that case as the frontend should treat it as pending-removed.
    """

def edit_by_id(
    in_queue: OrderedItemStore[TtsItem],
    pcm_queue: OrderedItemStore[PcmItem],
    item_id: str,
    new_text: str,
    new_speech_prompt: str | None | _UnsetType,  # sentinel for "don't change"
) -> tuple[str, TtsItem, str | None] | None:
    """Edit text/prompt of an item.

    - If in in_queue (pending): rewrites text+prompt in place. Returns ("pending", updated_item, None).
    - If in pcm_queue (synthesized): removes the PcmItem, constructs a new TtsItem with
      the new text and urgent flag preserved, appends to in_queue tail. Returns
      ("pending", new_item, old_id). Caller publishes tts_edited with new_id=new_item.id.
    - If not found in either: returns None (caller → 404).
    """

def reorder_stage(
    in_queue: OrderedItemStore[TtsItem],
    pcm_queue: OrderedItemStore[PcmItem],
    stage: str,  # "pending" | "synthesized"
    ids: list[str],
) -> bool:
    """Reorder items within one stage. Fails fast if `ids` set doesn't match the
    stage's current id set exactly.
    
    Returns False (→ caller 400) if ids set mismatch; True on success.
    """
```

`_UnsetType` is a module-level sentinel constant to distinguish "don't touch speech_prompt" from "set to None":

```python
class _UnsetType: pass
UNSET = _UnsetType()
```

`in_flight` is a `dict[str, TtsItem]` owned by SessionManager; helpers don't allocate it. Task 3 wires this registry through the synth thread.

Cancel flag: we need to set a flag on a TtsItem that survives the `get()` → synthesize → `put()` sequence. Simplest option: add `cancel_flag: bool = False` field on TtsItem (Task 1 of PR 2 already widened the dataclass; one more field is fine). The synth thread checks `item.cancel_flag` after the Google TTS call returns and skips `pcm_queue.put`.

- [ ] **Step 1: Add `cancel_flag` field on TtsItem and write failing tests**

First, add the `cancel_flag` field. In `src/live/tts_player.py`, find:

```python
@dataclasses.dataclass
class TtsItem:
    id: str
    text: str
    speech_prompt: str | None
    stage: str = "pending"       # "pending" | "synthesized"
    urgent: bool = False
```

Add `cancel_flag`:

```python
@dataclasses.dataclass
class TtsItem:
    id: str
    text: str
    speech_prompt: str | None
    stage: str = "pending"       # "pending" | "synthesized"
    urgent: bool = False
    cancel_flag: bool = False    # set by remove() when the item is in-flight
```

Then create `src/live/tts_mutations_test.py`:

```python
"""Tests for the pure-function cross-container TTS mutations."""
from __future__ import annotations

import numpy as np
import pytest

from src.live.tts_mutations import UNSET, edit_by_id, remove_by_id, reorder_stage
from src.live.tts_player import PcmItem, TtsItem
from src.shared.ordered_item_store import OrderedItemStore


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
    # in_flight dict itself not modified — synth thread clears it


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
    assert updated.speech_prompt == "prompt-old"  # UNSET preserves
    assert updated.urgent is True  # preserved
    assert old_id is None  # no id swap in pending path


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
    assert new_item.id != "old-id"  # new UUID
    assert new_item.text == "new"
    assert new_item.urgent is True  # preserved from pcm
    assert pcm_q.qsize() == 0  # PCM discarded
    assert in_q.qsize() == 1  # new item enqueued
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

    # Missing an id — must reject, not silently reorder a subset
    assert reorder_stage(in_q, pcm_q, "pending", [a.id]) is False
    # Set unchanged
    assert [it.id for it in in_q.snapshot()] == [a.id, b.id]


def test_reorder_fails_on_unknown_stage():
    in_q: OrderedItemStore = OrderedItemStore()
    pcm_q: OrderedItemStore = OrderedItemStore()
    assert reorder_stage(in_q, pcm_q, "playing", []) is False
```

- [ ] **Step 2: Run tests — must fail**

```bash
uv run pytest src/live/tts_mutations_test.py -v
```

Expected: `ImportError: cannot import name 'remove_by_id' from 'src.live.tts_mutations'`.

- [ ] **Step 3: Implement `src/live/tts_mutations.py`**

```python
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
    """Remove an item by id from whichever container holds it.

    Returns (stage, removed_item) if found, None otherwise.
    When the item is mid-synthesis (in_flight), sets cancel_flag=True on it —
    the synth thread will see the flag after Google TTS returns and skip
    the pcm_queue.put. From the frontend's perspective the item appears as
    'pending-removed', so stage="pending".
    """
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
    """Edit an item's text (and optionally speech_prompt).

    Returns (stage, item, old_id_if_reassigned).

    - Pending hit: in-place edit. old_id_if_reassigned=None.
    - Synthesized hit: discard PCM, construct a new TtsItem with a fresh UUID
      (carrying urgent flag from the PcmItem), enqueue at in_queue tail,
      return old_id_if_reassigned=old_id so the frontend can retire the old card.
    - Miss: None.
    """
    # pending path: in-place
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
        # refetch so we return the updated item
        updated = next((it for it in in_queue.snapshot() if it.id == item_id), None)
        if updated is not None:
            return ("pending", updated, None)

    # synthesized path: discard PCM + new pending
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
    """Reorder items within a single stage. Must be an exact id-set match.

    Returns True on success, False on stage-unknown or id-set mismatch.
    Callers surface False as HTTP 400.
    """
    if stage == "pending":
        container: OrderedItemStore = in_queue
    elif stage == "synthesized":
        container = pcm_queue
    else:
        return False

    current_ids = [it.id for it in container.snapshot()]
    if set(current_ids) != set(ids) or len(current_ids) != len(ids):
        return False

    # Use move() for each id — O(n^2) but n is small (<50)
    for target_index, item_id in enumerate(ids):
        container.move(item_id, target_index)
    return True
```

- [ ] **Step 4: Run tests — all must pass**

```bash
uv run pytest src/live/tts_mutations_test.py -v
```

Expected: 11 passed.

Run the full live suite to catch any accidental regression from the `cancel_flag` field addition:

```bash
uv run pytest src/ -q
```

Expected: all pass.

Ruff:

```bash
uv run ruff check src/live/tts_mutations.py src/live/tts_mutations_test.py src/live/tts_player.py
```

Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add src/live/tts_mutations.py src/live/tts_mutations_test.py src/live/tts_player.py
git commit -m "feat(tts): cross-container mutation helpers + cancel_flag field"
```

---

## Task 2: Make `_run_synth` honor the cancel_flag

**Files:**
- Modify: `src/live/tts_player.py`
- Modify: `src/live/tts_player_item_fields_test.py`

### Context

Task 1 sets `cancel_flag=True` on an item that's already been `.get()`-ed by the synth thread but not yet put into pcm_queue. The synth thread must see the flag AFTER the Google TTS call returns and BEFORE the `self._pcm_queue.put(pcm_item)` line, so it discards the PCM (which was wasted work anyway).

There's also the `in_flight` registry: the synth thread needs to **register** the item right after `get()` and **clear** it right before `put()` so `remove_by_id` can find it at the correct moment.

- [ ] **Step 1: Explore current `_run_synth` and plan the minimal change**

Read `src/live/tts_player.py` `_run_synth` (around lines 235-295). Identify:
- Where `self._queue.get()` returns an item.
- Where `self._pcm_queue.put(pcm_item)` and the `on_synthesized` fire live.

The registry will be an attribute on TTSPlayer: `self._in_flight: dict[str, TtsItem]` + a lock. SessionManager will `get_in_flight_ref()` to pass it to `remove_by_id`.

- [ ] **Step 2: Write the failing test**

Append to `src/live/tts_player_item_fields_test.py`:

```python
def test_tts_player_exposes_in_flight_registry():
    """The TTSPlayer exposes a dict[id → TtsItem] for items currently being synthesized.
    Consumers (SessionManager) pass this dict into tts_mutations.remove_by_id."""
    player = TTSPlayer(
        in_queue=OrderedItemStore(),
        speak_fn=lambda _t, _p: None,
    )
    ref = player.get_in_flight_ref()
    assert isinstance(ref, dict)
    assert ref is player.get_in_flight_ref()  # same reference each time
```

(We don't test the synth thread's use of the registry directly — the real GCP path is too heavy for a unit test. The integration is covered by the manual e2e in the final task.)

- [ ] **Step 3: Run test — must fail**

```bash
uv run pytest src/live/tts_player_item_fields_test.py::test_tts_player_exposes_in_flight_registry -v
```

Expected: `AttributeError: 'TTSPlayer' object has no attribute 'get_in_flight_ref'`.

- [ ] **Step 4: Add registry + wire `_run_synth`**

In `TTSPlayer.__init__`, after the existing `self._is_speaking = False` line, add:

```python
        self._in_flight: dict[str, TtsItem] = {}
        self._in_flight_lock = threading.Lock()
```

Add a public accessor below the other public methods (above `put` is fine):

```python
    def get_in_flight_ref(self) -> dict:
        """Return the in-flight registry (dict of items currently being synthesized).

        SessionManager passes this into tts_mutations.remove_by_id so cancellations
        can race-safely mark items that have already been get()-ed but not yet put().
        """
        return self._in_flight
```

In `_run_synth`, modify the loop. Find the block:

```python
            item = self._queue.get(timeout=0.2)
            ...
            if item is _SENTINEL:
                ...
                break
            ...
            logger.info("[TTS] Synthesizing: %s", item.text[:60])
            try:
                response = client.synthesize_speech(...)
            except Exception as e:
                logger.error("[TTS] Synthesis failed: %s", e)
                self._queue.task_done()
                continue
            ...
            pcm_item = PcmItem(...)
            self._queue.task_done()
            self._pcm_queue.put(pcm_item)
            if self._on_synthesized:
                self._on_synthesized(pcm_item)
```

Wrap with registry registration and cancel-flag check:

```python
            item = self._queue.get(timeout=0.2)
            ...
            if item is _SENTINEL:
                ...
                break
            ...
            # Register as in-flight so cross-container remove can find it
            with self._in_flight_lock:
                self._in_flight[item.id] = item

            logger.info("[TTS] Synthesizing: %s", item.text[:60])
            try:
                response = client.synthesize_speech(...)
            except Exception as e:
                logger.error("[TTS] Synthesis failed: %s", e)
                self._queue.task_done()
                with self._in_flight_lock:
                    self._in_flight.pop(item.id, None)
                continue
            ...
            pcm_item = PcmItem(...)
            self._queue.task_done()

            with self._in_flight_lock:
                self._in_flight.pop(item.id, None)

            if item.cancel_flag:
                logger.info("[TTS] Cancelled in-flight item %s, discarding PCM", item.id)
                continue

            self._pcm_queue.put(pcm_item)
            if self._on_synthesized:
                self._on_synthesized(pcm_item)
```

Do NOT change `_run_mock` or `_run_fallback` — they don't go through `pcm_queue`, so in-flight tracking is not needed (remove on a mock item can always find it in `in_queue`).

- [ ] **Step 5: Run test + full suite**

```bash
uv run pytest src/live/tts_player_item_fields_test.py -v
```

Expected: 9 passed (8 existing + 1 new).

```bash
uv run pytest src/ -q
```

Expected: all pass.

Ruff clean:

```bash
uv run ruff check src/live/tts_player.py src/live/tts_player_item_fields_test.py
```

- [ ] **Step 6: Commit**

```bash
git add src/live/tts_player.py src/live/tts_player_item_fields_test.py
git commit -m "feat(tts): in_flight registry + cancel_flag honored in _run_synth"
```

---

## Task 3: SessionManager mutation methods + SSE events

**Files:**
- Modify: `src/live/session.py`
- Modify: `src/live/session_tts_events_test.py`

### Context

SessionManager exposes `remove_tts(id)`, `edit_tts(id, text, speech_prompt)`, `reorder_tts(stage, ids)`. Each calls the Task-1 helper with the right containers + publishes an SSE event.

SSE events:

| Event | Payload |
|---|---|
| `tts_removed` | `{id, stage, ts}` |
| `tts_edited` | `{id, new_id: str \| None, content, speech_prompt, stage, ts}` |
| `tts_reordered` | `{stage, ids: list[str], ts}` |

Extract publisher helpers (matching the Task-3 pattern from PR 2):

```python
def _publish_tts_removed(bus, item_id: str, stage: str) -> None: ...
def _publish_tts_edited(bus, new_item: TtsItem, old_id: str | None, stage: str) -> None: ...
def _publish_tts_reordered(bus, stage: str, ids: list[str]) -> None: ...
```

- [ ] **Step 1: Write failing tests for the helpers**

Append to `src/live/session_tts_events_test.py`:

```python
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


def test_publish_tts_edited_with_new_id(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_edited

    new_item = TtsItem.create("rewritten", "prompt-b", urgent=True)
    _publish_tts_edited(bus, new_item, old_id="old-x", stage="pending")

    assert len(collected) == 1
    ev = collected[0]
    assert ev["type"] == "tts_edited"
    assert ev["id"] == new_item.id
    assert ev["new_id"] is None  # new_id is "this is the final id" — only set when differs
    # Actually revise: spec says new_id is the post-edit id. Adjust semantics below.
```

Wait — the spec says the event carries `new_id` as the **new** id when an id swap happened (synthesized→pending path). Let me restate the shape clearly:

- `tts_edited` payload is always: `{type, id, new_id, content, speech_prompt, stage, ts}` where
  - `id` = the id the frontend should **update or replace**. For pending in-place edits, `id == new_id`. For synthesized→pending edits, `id` = old id (about to be removed), `new_id` = the new TtsItem's id.
- Simpler alternative (clearer for the frontend reducer): always use `id` as the pre-existing card id and `new_id` as the replacement. When no swap, `new_id = id`.

Use the simpler form. Rewrite the test:

```python
def test_publish_tts_edited_in_place(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_edited

    edited = TtsItem.create("rewritten", "prompt-b", urgent=False)
    # In-place edit: old_id is None; event's id == edited.id, new_id == edited.id
    _publish_tts_edited(bus, edited, old_id=None, stage="pending")

    ev = collected[0]
    assert ev["type"] == "tts_edited"
    assert ev["id"] == edited.id
    assert ev["new_id"] == edited.id  # no swap
    assert ev["content"] == "rewritten"
    assert ev["speech_prompt"] == "prompt-b"
    assert ev["stage"] == "pending"


def test_publish_tts_edited_with_id_swap(bus_with_collector):
    bus, collected = bus_with_collector
    from src.live.session import _publish_tts_edited

    new_item = TtsItem.create("rewritten", None, urgent=True)
    # synthesized → pending: event's id is the old id; new_id is the replacement
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
```

Also write tests for the SessionManager methods:

```python
def test_session_remove_tts_finds_pending_and_publishes():
    """SessionManager.remove_tts delegates to tts_mutations + publishes tts_removed."""
    from src.live.session import SessionManager

    class _StubBus:
        def __init__(self): self.events: list[dict] = []
        def publish(self, ev): self.events.append(ev)

    bus = _StubBus()
    mgr = SessionManager(bus)
    mgr._running = True

    # Stub containers with an in-flight-less scenario
    from src.shared.ordered_item_store import OrderedItemStore
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

    class _StubBus:
        def publish(self, _ev): pass

    mgr = SessionManager(_StubBus())
    mgr._running = True

    from src.shared.ordered_item_store import OrderedItemStore

    class _StubPlayer:
        def __init__(self): self._pcm_queue = OrderedItemStore()
        def get_in_flight_ref(self): return {}

    mgr._tts_queue = OrderedItemStore()
    mgr._tts_player = _StubPlayer()

    assert mgr.remove_tts("ghost") is False
```

(Similar tests for `edit_tts` and `reorder_tts` — add one happy-path + one not-found for each.)

Append two more:

```python
def test_session_edit_tts_pending_updates_in_place():
    from src.live.session import SessionManager
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

    ok = mgr.edit_tts(item.id, "new", UNSET_MARKER := object())  # see below
    assert ok is True
    assert in_q.snapshot()[0].text == "new"
    assert any(e["type"] == "tts_edited" and e["id"] == item.id for e in bus.events)


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
```

(For the edit test, use the exported `UNSET` from `tts_mutations` instead of the inline `UNSET_MARKER := object()` placeholder. Replace with `from src.live.tts_mutations import UNSET` at the top of the test file and pass `UNSET` as the third arg.)

- [ ] **Step 2: Run tests — must fail**

```bash
uv run pytest src/live/session_tts_events_test.py -v
```

Expected: new tests fail (`ImportError` / `AttributeError`).

- [ ] **Step 3: Add publisher helpers + SessionManager methods**

In `src/live/session.py`, after the existing `_publish_tts_synthesized` helper, add:

```python
def _publish_tts_removed(bus, item_id: str, stage: str) -> None:
    bus.publish({
        "type": "tts_removed",
        "id": item_id,
        "stage": stage,
        "ts": time.time(),
    })


def _publish_tts_edited(bus, new_item: "TtsItem", old_id: str | None, stage: str) -> None:
    """Publish tts_edited.

    - In-place edit: old_id is None. Event's id == new_id == new_item.id.
    - Id swap (synth→pending): old_id is the pre-swap id. Event's id = old_id,
      new_id = new_item.id. Frontend retires the old card and renders the new.
    """
    effective_id = old_id if old_id is not None else new_item.id
    bus.publish({
        "type": "tts_edited",
        "id": effective_id,
        "new_id": new_item.id,
        "content": new_item.text,
        "speech_prompt": new_item.speech_prompt,
        "stage": stage,
        "ts": time.time(),
    })


def _publish_tts_reordered(bus, stage: str, ids: list[str]) -> None:
    bus.publish({
        "type": "tts_reordered",
        "stage": stage,
        "ids": ids,
        "ts": time.time(),
    })
```

Add the three `SessionManager` methods (anywhere after `get_tts_queue_snapshot`):

```python
    def remove_tts(self, item_id: str) -> bool:
        from src.live.tts_mutations import remove_by_id

        with self._lock:
            if not self._running:
                return False
            q = self._tts_queue
            player = self._tts_player
        if q is None or player is None:
            return False

        result = remove_by_id(q, player._pcm_queue, player.get_in_flight_ref(), item_id)
        if result is None:
            return False
        stage, _ = result
        _publish_tts_removed(self._bus, item_id, stage)
        return True

    def edit_tts(self, item_id: str, new_text: str, new_speech_prompt) -> bool:
        from src.live.tts_mutations import edit_by_id

        with self._lock:
            if not self._running:
                return False
            q = self._tts_queue
            player = self._tts_player
        if q is None or player is None:
            return False

        result = edit_by_id(q, player._pcm_queue, item_id, new_text, new_speech_prompt)
        if result is None:
            return False
        stage, new_item, old_id = result
        _publish_tts_edited(self._bus, new_item, old_id, stage)
        return True

    def reorder_tts(self, stage: str, ids: list[str]) -> bool:
        from src.live.tts_mutations import reorder_stage

        with self._lock:
            if not self._running:
                return False
            q = self._tts_queue
            player = self._tts_player
        if q is None or player is None:
            return False

        ok = reorder_stage(q, player._pcm_queue, stage, ids)
        if not ok:
            return False
        _publish_tts_reordered(self._bus, stage, ids)
        return True
```

- [ ] **Step 4: Run tests — must pass**

```bash
uv run pytest src/live/session_tts_events_test.py -v
```

Expected: all pass.

Full suite:

```bash
uv run pytest src/ -q
```

Expected: all pass.

Ruff: no new errors.

- [ ] **Step 5: Commit**

```bash
git add src/live/session.py src/live/session_tts_events_test.py
git commit -m "feat(session): remove_tts/edit_tts/reorder_tts + 3 new SSE events"
```

---

## Task 4: REST endpoints for the mutations

**Files:**
- Modify: `src/live/routes.py`
- Modify: `src/live/routes_test.py`

### Context

Three endpoints matching the SessionManager methods. Shape:

| Method | Path | Body | Success | Failure |
|---|---|---|---|---|
| `DELETE` | `/live/tts/queue/{id}` | — | 200 `{ok: true}` | 404 |
| `PATCH` | `/live/tts/queue/{id}` | `{text, speech_prompt?}` | 200 `{ok: true}` | 404 |
| `POST` | `/live/tts/queue/reorder` | `{stage, ids}` | 200 `{ok: true}` | 400 (stage unknown or ids mismatch) |

The SSE event is published inside SessionManager; the endpoint just returns the boolean.

- [ ] **Step 1: Write failing tests**

Append to `src/live/routes_test.py`:

```python
def test_delete_tts_queue_item_returns_404_when_not_running(client):
    response = client.delete("/live/tts/queue/any-id")
    assert response.status_code == 404


def test_patch_tts_queue_item_returns_404_when_not_running(client):
    response = client.patch("/live/tts/queue/any-id", json={"text": "new"})
    assert response.status_code == 404


def test_reorder_tts_queue_returns_400_when_not_running(client):
    response = client.post(
        "/live/tts/queue/reorder",
        json={"stage": "pending", "ids": []},
    )
    assert response.status_code == 400


def test_patch_tts_queue_requires_text(client):
    """Missing `text` in body → FastAPI 422."""
    response = client.patch("/live/tts/queue/x", json={})
    assert response.status_code == 422


def test_reorder_tts_queue_requires_stage_and_ids(client):
    response = client.post("/live/tts/queue/reorder", json={"stage": "pending"})
    assert response.status_code == 422
```

(Happy-path tests would require a running session with items — too heavy for unit. Covered by manual e2e + the Task 3 SessionManager unit tests.)

- [ ] **Step 2: Run tests — must fail**

```bash
uv run pytest src/live/routes_test.py -v
```

Expected: the 5 new tests fail with 404 (endpoint not yet added) or 422 validation errors missing.

- [ ] **Step 3: Add Pydantic bodies + endpoints in `routes.py`**

Near the existing `InjectBody` pydantic model, add:

```python
class EditTtsBody(BaseModel):
    text: str
    speech_prompt: str | None | None = None  # None-allowed; "unset" handled via UNSET sentinel


class ReorderTtsBody(BaseModel):
    stage: str
    ids: list[str]
```

(Confirm `from pydantic import BaseModel` is already imported at the top.)

Actually — to distinguish "don't change prompt" from "set prompt to None" over HTTP, we'll use a field default sentinel. Pydantic doesn't support Python sentinels directly, so use a specially-typed field:

```python
class EditTtsBody(BaseModel):
    text: str
    speech_prompt: str | None = None  # explicit None = set to None; omit field = unset
    
    # Note: FastAPI/Pydantic will populate speech_prompt=None either way (field default),
    # so to distinguish "explicit None" from "absent", use model_dump(exclude_unset=True).
```

The handler does:

```python
body_dict = body.model_dump(exclude_unset=True)
prompt = body_dict.get("speech_prompt", UNSET)
```

Then add the 3 endpoints after the existing `/tts/queue/snapshot`:

```python
@router.delete("/tts/queue/{item_id}")
def delete_tts_item(
    item_id: str,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    ok = sm.remove_tts(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found or session not running")
    return {"ok": True}


@router.patch("/tts/queue/{item_id}")
def edit_tts_item(
    item_id: str,
    body: EditTtsBody,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    from src.live.tts_mutations import UNSET

    body_dict = body.model_dump(exclude_unset=True)
    prompt = body_dict.get("speech_prompt", UNSET)
    ok = sm.edit_tts(item_id, body.text, prompt)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found or session not running")
    return {"ok": True}


@router.post("/tts/queue/reorder")
def reorder_tts_items(
    body: ReorderTtsBody,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    ok = sm.reorder_tts(body.stage, body.ids)
    if not ok:
        raise HTTPException(status_code=400, detail="reorder rejected: stage unknown or ids mismatch")
    return {"ok": True}
```

- [ ] **Step 4: Run tests — must pass**

```bash
uv run pytest src/live/routes_test.py -v
```

Expected: all 5 new pass (plus the existing 1).

Full suite:

```bash
uv run pytest src/ -q
```

Ruff: no new errors.

- [ ] **Step 5: Commit**

```bash
git add src/live/routes.py src/live/routes_test.py
git commit -m "feat(routes): DELETE/PATCH/POST reorder endpoints for TTS queue"
```

---

## Task 5: Frontend `applyLiveEvent` handles 3 new events

**Files:**
- Modify: `apps/web/src/features/live/hooks/use-live-stream.ts`
- Modify: `apps/web/src/features/live/hooks/use-live-stream.test.ts`

### Context

`applyLiveEvent` currently handles `tts_queued / tts_synthesized / tts_playing / tts_done`. Add the 3 mutation events.

Semantics:

- `tts_removed`: filter out item by id.
- `tts_edited`: if `new_id !== id`, remove old id and append new pending item at tail; else patch content/speech_prompt in place.
- `tts_reordered`: for the given stage, reorder items in-place to match `ids`.

- [ ] **Step 1: Write failing tests**

Append to `use-live-stream.test.ts`:

```ts
  it('tts_removed filters out the matching id', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
      { id: 'b', content: 'ho', speech_prompt: null, stage: 'pending', urgent: false, ts: 2 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_removed', id: 'a', stage: 'pending', ts: 3 })
    expect(next).toHaveLength(1)
    expect(next[0].id).toBe('b')
  })

  it('tts_edited in-place updates content and speech_prompt when id == new_id', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'old', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, {
      type: 'tts_edited', id: 'a', new_id: 'a',
      content: 'new', speech_prompt: 'prompt', stage: 'pending', ts: 2,
    })
    expect(next[0].content).toBe('new')
    expect(next[0].speech_prompt).toBe('prompt')
  })

  it('tts_edited with id swap retires old and appends new pending', () => {
    const initial: PipelineItem[] = [
      { id: 'old', content: 'was-pcm', speech_prompt: null, stage: 'synthesized', urgent: true, ts: 1 },
    ]
    const next = applyLiveEvent(initial, {
      type: 'tts_edited', id: 'old', new_id: 'fresh',
      content: 'rewritten', speech_prompt: null, stage: 'pending', ts: 2,
    })
    expect(next.find((p) => p.id === 'old')).toBeUndefined()
    const fresh = next.find((p) => p.id === 'fresh')
    expect(fresh).toBeDefined()
    expect(fresh?.stage).toBe('pending')
    expect(fresh?.content).toBe('rewritten')
  })

  it('tts_reordered rearranges items within a stage while preserving other stages', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'A', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
      { id: 'b', content: 'B', speech_prompt: null, stage: 'pending', urgent: false, ts: 2 },
      { id: 'c', content: 'C', speech_prompt: null, stage: 'synthesized', urgent: false, ts: 3 },
    ]
    const next = applyLiveEvent(initial, {
      type: 'tts_reordered', stage: 'pending', ids: ['b', 'a'], ts: 4,
    })
    const pending = next.filter((p) => p.stage === 'pending').map((p) => p.id)
    expect(pending).toEqual(['b', 'a'])
    const synth = next.filter((p) => p.stage === 'synthesized')
    expect(synth).toHaveLength(1)
    expect(synth[0].id).toBe('c')
  })
```

- [ ] **Step 2: Run — must fail**

```bash
pnpm --filter web test use-live-stream
```

Expected: 4 new fail (same reference returned because `applyLiveEvent` doesn't recognize the types).

- [ ] **Step 3: Extend `applyLiveEvent`**

Add branches inside the existing function, right before the final `return prev`:

```ts
  if (type === 'tts_removed' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    if (idx < 0) return prev
    return prev.filter((p) => p.id !== id)
  }

  if (type === 'tts_edited' && id) {
    const newId = raw['new_id'] as string | undefined
    const content = raw['content'] as string | undefined
    const speech_prompt = (raw['speech_prompt'] as string | null | undefined) ?? null
    const idx = prev.findIndex((p) => p.id === id)

    if (newId && newId !== id) {
      // id swap: retire old, append new at pending tail
      const filtered = prev.filter((p) => p.id !== id)
      return [
        ...filtered,
        {
          id: newId,
          content: content ?? '',
          speech_prompt,
          stage: (raw['stage'] as PipelineStage) ?? 'pending',
          urgent: Boolean(raw['urgent']),
          ts: (raw['ts'] as number) ?? Date.now() / 1000,
        },
      ]
    }

    if (idx < 0) return prev
    const updated = [...prev]
    updated[idx] = {
      ...updated[idx],
      content: content ?? updated[idx].content,
      speech_prompt,
    }
    return updated
  }

  if (type === 'tts_reordered') {
    const stage = raw['stage'] as PipelineStage
    const ids = raw['ids'] as string[] | undefined
    if (!ids || !Array.isArray(ids)) return prev

    const staged = prev.filter((p) => p.stage === stage)
    if (staged.length !== ids.length) return prev
    const byId = new Map(staged.map((p) => [p.id, p]))
    if (ids.some((id_) => !byId.has(id_))) return prev

    const reorderedStage: PipelineItem[] = ids.map((id_) => byId.get(id_)!)
    const others = prev.filter((p) => p.stage !== stage)

    // Preserve relative positions: we emit others first then the reordered stage.
    // This simplifies the reducer; consumers filter by stage anyway so absolute
    // order within the combined array doesn't matter for derived views.
    return [...others, ...reorderedStage]
  }
```

- [ ] **Step 4: Run — must pass**

```bash
pnpm --filter web test use-live-stream
```

Expected: 10 passed.

Type check + lint.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/live/hooks/use-live-stream.ts apps/web/src/features/live/hooks/use-live-stream.test.ts
git commit -m "feat(live): handle tts_removed/edited/reordered events in reducer"
```

---

## Task 6: `useTtsMutations` hook for the three REST calls

**Files:**
- Create: `apps/web/src/features/live/hooks/use-tts-mutations.ts`
- Create: `apps/web/src/features/live/hooks/use-tts-mutations.test.ts`

### Context

Encapsulate the three REST calls. Optimistic updates are done by the components (via `applyLiveEvent`-shaped optimistic events); the hook returns `{remove, edit, reorder, loading}` and toasts on failure.

- [ ] **Step 1: Write failing test**

Create `apps/web/src/features/live/hooks/use-tts-mutations.test.ts`:

```ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useTtsMutations } from './use-tts-mutations'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

const toastError = vi.fn()
vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: toastError, success: vi.fn() },
}))

describe('useTtsMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('remove calls DELETE /live/tts/queue/:id', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.remove('abc') })
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/live/tts/queue/abc', expect.objectContaining({ method: 'DELETE' }))
  })

  it('edit PATCHes with text and optional speech_prompt', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.edit('x', { text: 'new', speech_prompt: 'p' }) })
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/live/tts/queue/x',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ text: 'new', speech_prompt: 'p' }),
      }),
    )
  })

  it('edit omits speech_prompt when undefined', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.edit('x', { text: 'new' }) })
    const call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(JSON.parse(call[1].body)).toEqual({ text: 'new' })
  })

  it('reorder posts stage + ids', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.reorder('pending', ['a', 'b']) })
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/live/tts/queue/reorder',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ stage: 'pending', ids: ['a', 'b'] }),
      }),
    )
  })

  it('on 4xx, toasts error and returns false', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: 'nope' }) })
    const { result } = renderHook(() => useTtsMutations())
    let ok: boolean | undefined
    await act(async () => { ok = await result.current.remove('ghost') })
    expect(ok).toBe(false)
    await waitFor(() => expect(toastError).toHaveBeenCalled())
  })
})
```

- [ ] **Step 2: Run — must fail**

```bash
pnpm --filter web test use-tts-mutations
```

- [ ] **Step 3: Implement the hook**

Create `apps/web/src/features/live/hooks/use-tts-mutations.ts`:

```ts
'use client'

import { useCallback, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { env } from '@/config/env'

type EditPatch = { text: string; speech_prompt?: string | null }

export function useTtsMutations() {
  const [loading, setLoading] = useState(false)

  const remove = useCallback(async (id: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/${id}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast.error(typeof data.detail === 'string' ? data.detail : '删除失败')
        return false
      }
      return true
    } catch {
      toast.error('无法连接到后端')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const edit = useCallback(async (id: string, patch: EditPatch): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/${id}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(patch),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast.error(typeof data.detail === 'string' ? data.detail : '编辑失败')
        return false
      }
      return true
    } catch {
      toast.error('无法连接到后端')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const reorder = useCallback(async (stage: 'pending' | 'synthesized', ids: string[]): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/reorder`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ stage, ids }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast.error(typeof data.detail === 'string' ? data.detail : '顺序已过时，请重试')
        return false
      }
      return true
    } catch {
      toast.error('无法连接到后端')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  return { remove, edit, reorder, loading }
}
```

- [ ] **Step 4: Run — must pass**

```bash
pnpm --filter web test use-tts-mutations
```

Expected: 5 passed.

Type check + lint.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/live/hooks/use-tts-mutations.ts apps/web/src/features/live/hooks/use-tts-mutations.test.ts
git commit -m "feat(live): useTtsMutations hook for REST mutations"
```

---

## Task 7: `BroadcastPipeline` component (pure rendering, no drag yet)

**Files:**
- Create: `apps/web/src/features/live/components/broadcast-pipeline/index.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/pipeline-header.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/stage-section.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/pipeline-item.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/pipeline-item-editor.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/now-playing-card.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/history-section.tsx`
- Create: `apps/web/src/features/live/components/broadcast-pipeline/broadcast-pipeline.test.tsx`

### Context

Ship the static tree first — no drag, no animations. Task 8 adds drag; Task 9 adds motion. Props:

```ts
type Props = {
  pending: PipelineItem[]
  synthesized: PipelineItem[]
  nowPlaying: PipelineItem | null  // derive from raw PipelineItem instead of AiOutput to access urgent
  history: PipelineItem[]
  llmGenerating: boolean
  ttsSpeaking: boolean
  urgentCount: number
}
```

(Note: `use-live-stream` currently returns `nowPlaying: AiOutput | null`. We add a new return `nowPlayingItem: PipelineItem | null` derived from pipeline in a separate commit or as part of this task — see Step 6.)

- [ ] **Step 1: Write a minimal smoke test first**

Create `apps/web/src/features/live/components/broadcast-pipeline/broadcast-pipeline.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'
import { BroadcastPipeline } from './index'

vi.mock('@/features/live/hooks/use-tts-mutations', () => ({
  useTtsMutations: () => ({ remove: vi.fn(), edit: vi.fn(), reorder: vi.fn(), loading: false }),
}))

const _mk = (id: string, stage: PipelineItem['stage'], content = id): PipelineItem => ({
  id, content, speech_prompt: null, stage, urgent: false, ts: 0,
})

describe('BroadcastPipeline', () => {
  it('renders all four stages', () => {
    render(
      <BroadcastPipeline
        pending={[_mk('p1', 'pending')]}
        synthesized={[_mk('s1', 'synthesized')]}
        nowPlayingItem={_mk('play1', 'playing')}
        history={[_mk('d1', 'done')]}
        llmGenerating={false}
        ttsSpeaking={true}
        urgentCount={0}
      />,
    )

    expect(screen.getByText('p1')).toBeInTheDocument()
    expect(screen.getByText('s1')).toBeInTheDocument()
    expect(screen.getByText('play1')).toBeInTheDocument()
  })

  it('renders urgent badge when urgent item present', () => {
    render(
      <BroadcastPipeline
        pending={[{ ..._mk('u', 'pending'), urgent: true }]}
        synthesized={[]}
        nowPlayingItem={null}
        history={[]}
        llmGenerating={false}
        ttsSpeaking={false}
        urgentCount={1}
      />,
    )

    expect(screen.getByTestId('urgent-badge-u')).toBeInTheDocument()
  })

  it('shows "generating" indicator when llmGenerating', () => {
    render(
      <BroadcastPipeline
        pending={[]}
        synthesized={[]}
        nowPlayingItem={null}
        history={[]}
        llmGenerating={true}
        ttsSpeaking={false}
        urgentCount={0}
      />,
    )
    expect(screen.getByTestId('llm-generating-indicator')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — must fail**

```bash
pnpm --filter web test broadcast-pipeline
```

- [ ] **Step 3: Scaffold the components**

Create each file. Keep styling consistent with the existing components (read `ai-status-card.tsx` and `tts-queue-panel.tsx` for patterns and Tailwind classes):

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/pipeline-header.tsx
'use client'

import { cn } from '@workspace/ui/lib/utils'

type Props = {
  llmGenerating: boolean
  ttsSpeaking: boolean
  pendingCount: number
  synthesizedCount: number
  urgentCount: number
}

export function PipelineHeader({ llmGenerating, ttsSpeaking, pendingCount, synthesizedCount, urgentCount }: Props) {
  return (
    <div className="flex items-center justify-between rounded-t-lg border-b bg-background px-4 py-2 text-xs">
      <div className="flex items-center gap-3">
        <span
          data-testid="llm-generating-indicator"
          className={cn('flex items-center gap-1', llmGenerating ? 'text-blue-500' : 'text-muted-foreground', !llmGenerating && 'hidden')}
        >
          <span className="size-1.5 animate-pulse rounded-full bg-blue-500" />
          生成中
        </span>
        <span className={cn('flex items-center gap-1', ttsSpeaking ? 'text-green-500' : 'text-muted-foreground')}>
          <span className={cn('size-1.5 rounded-full', ttsSpeaking ? 'animate-pulse bg-green-500' : 'bg-muted-foreground/30')} />
          {ttsSpeaking ? '播报中' : '播报待机'}
        </span>
      </div>
      <div className="flex items-center gap-3 tabular-nums text-muted-foreground">
        <span>待合成 {pendingCount}</span>
        <span>已合成 {synthesizedCount}</span>
        {urgentCount > 0 && <span className="text-amber-500">紧急 {urgentCount}</span>}
      </div>
    </div>
  )
}
```

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/pipeline-item.tsx
'use client'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { PencilIcon, TrashIcon } from 'lucide-react'
import { useState } from 'react'

import type { PipelineItem as PipelineItemType } from '@/features/live/hooks/use-live-stream'

import { PipelineItemEditor } from './pipeline-item-editor'

type Props = {
  item: PipelineItemType
  onRemove: (id: string) => void
  onEdit: (id: string, text: string, speech_prompt: string | null) => void
}

export function PipelineItem({ item, onRemove, onEdit }: Props) {
  const [editing, setEditing] = useState(false)

  return (
    <>
      <div
        className={cn(
          'group relative rounded-md border px-3 py-2 text-sm',
          item.stage === 'pending' && 'bg-muted/20',
          item.stage === 'synthesized' && 'border-border bg-muted/40',
        )}
      >
        {item.urgent && <span data-testid={`urgent-badge-${item.id}`} className="absolute left-1 top-1 size-2 rounded-full bg-red-500" />}
        <p className="leading-relaxed">{item.content}</p>
        {item.speech_prompt && <p className="mt-0.5 text-[10px] text-muted-foreground">{item.speech_prompt}</p>}
        <div className="pointer-events-none absolute right-2 top-1/2 flex -translate-y-1/2 gap-1 opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100">
          <Button size="icon" variant="ghost" className="size-6" aria-label="编辑" onClick={() => setEditing(true)}>
            <PencilIcon className="size-3" />
          </Button>
          <Button size="icon" variant="ghost" className="size-6 text-destructive" aria-label="删除" onClick={() => onRemove(item.id)}>
            <TrashIcon className="size-3" />
          </Button>
        </div>
      </div>
      {editing && (
        <PipelineItemEditor
          item={item}
          onSave={(text, prompt) => { onEdit(item.id, text, prompt); setEditing(false) }}
          onCancel={() => setEditing(false)}
        />
      )}
    </>
  )
}
```

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/pipeline-item-editor.tsx
'use client'

import { Button } from '@workspace/ui/components/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@workspace/ui/components/dialog'
import { Label } from '@workspace/ui/components/label'
import { Textarea } from '@workspace/ui/components/textarea'
import { useState } from 'react'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

type Props = {
  item: PipelineItem
  onSave: (text: string, speech_prompt: string | null) => void
  onCancel: () => void
}

export function PipelineItemEditor({ item, onSave, onCancel }: Props) {
  const [text, setText] = useState(item.content)
  const [prompt, setPrompt] = useState(item.speech_prompt ?? '')

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑话术</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          <div>
            <Label>文本（{text.length} 字）</Label>
            <Textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div>
            <Label>语音提示（可选）</Label>
            <Textarea rows={2} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </div>
          {item.stage === 'synthesized' && (
            <p className="rounded-md bg-amber-500/10 p-2 text-xs text-amber-600">
              注意：此条已合成音频。保存后将重新合成并加入待合成队列末尾。
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>取消</Button>
          <Button onClick={() => onSave(text, prompt || null)}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/stage-section.tsx
'use client'

import type { PipelineItem as PipelineItemType } from '@/features/live/hooks/use-live-stream'
import { PipelineItem } from './pipeline-item'

type Props = {
  title: string
  items: PipelineItemType[]
  onRemove: (id: string) => void
  onEdit: (id: string, text: string, speech_prompt: string | null) => void
}

export function StageSection({ title, items, onRemove, onEdit }: Props) {
  return (
    <section className="flex flex-col gap-1.5 p-3">
      <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <span>{title}</span>
        <span>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">—</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {items.map((item) => (
            <PipelineItem key={item.id} item={item} onRemove={onRemove} onEdit={onEdit} />
          ))}
        </div>
      )}
    </section>
  )
}
```

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/now-playing-card.tsx
'use client'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

export function NowPlayingCard({ item }: { item: PipelineItem | null }) {
  return (
    <div className="border-y bg-primary/5 p-3">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="size-1.5 animate-pulse rounded-full bg-primary" />
        <span className="text-[10px] font-medium text-primary">正在播</span>
      </div>
      {item ? (
        <>
          <p className="text-sm leading-relaxed">{item.content}</p>
          {item.speech_prompt && <p className="mt-0.5 text-[10px] text-muted-foreground">{item.speech_prompt}</p>}
        </>
      ) : (
        <p className="text-xs text-muted-foreground">等待 AI 输出…</p>
      )}
    </div>
  )
}
```

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/history-section.tsx
'use client'

import { ChevronDownIcon, ChevronUpIcon } from 'lucide-react'
import { useState } from 'react'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

export function HistorySection({ items }: { items: PipelineItem[] }) {
  const [open, setOpen] = useState(false)

  return (
    <section className="border-t">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
        onClick={() => setOpen((o) => !o)}
      >
        <span>已播完（{items.length}）</span>
        {open ? <ChevronUpIcon className="size-3" /> : <ChevronDownIcon className="size-3" />}
      </button>
      {open && (
        <div className="flex flex-col gap-1 px-3 pb-3">
          {items.slice(-100).reverse().map((item) => (
            <div key={item.id} className="rounded border border-dashed px-2 py-1 text-xs text-muted-foreground">
              {item.content}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
```

```tsx
// apps/web/src/features/live/components/broadcast-pipeline/index.tsx
'use client'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'
import { useTtsMutations } from '@/features/live/hooks/use-tts-mutations'

import { HistorySection } from './history-section'
import { NowPlayingCard } from './now-playing-card'
import { PipelineHeader } from './pipeline-header'
import { StageSection } from './stage-section'

type Props = {
  pending: PipelineItem[]
  synthesized: PipelineItem[]
  nowPlayingItem: PipelineItem | null
  history: PipelineItem[]
  llmGenerating: boolean
  ttsSpeaking: boolean
  urgentCount: number
}

export function BroadcastPipeline({ pending, synthesized, nowPlayingItem, history, llmGenerating, ttsSpeaking, urgentCount }: Props) {
  const { remove, edit } = useTtsMutations()

  const onRemove = (id: string) => void remove(id)
  const onEdit = (id: string, text: string, speech_prompt: string | null) => void edit(id, { text, speech_prompt })

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-background">
      <PipelineHeader
        llmGenerating={llmGenerating}
        ttsSpeaking={ttsSpeaking}
        pendingCount={pending.length}
        synthesizedCount={synthesized.length}
        urgentCount={urgentCount}
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-auto">
        <StageSection title="待合成" items={pending} onRemove={onRemove} onEdit={onEdit} />
        <StageSection title="已合成" items={synthesized} onRemove={onRemove} onEdit={onEdit} />
        <NowPlayingCard item={nowPlayingItem} />
        <HistorySection items={history} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run — must pass**

```bash
pnpm --filter web test broadcast-pipeline
```

Expected: 3 passed.

Type check + lint.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/live/components/broadcast-pipeline
git commit -m "feat(live): BroadcastPipeline component tree (no drag yet)"
```

---

## Task 8: In-stage drag-and-drop via pragmatic-drag-and-drop

**Files:**
- Modify: `apps/web/src/features/live/components/broadcast-pipeline/stage-section.tsx`
- Modify: `apps/web/src/features/live/components/broadcast-pipeline/pipeline-item.tsx`
- Modify: `apps/web/src/features/live/components/broadcast-pipeline/index.tsx`
- Modify: `apps/web/src/features/live/components/broadcast-pipeline/broadcast-pipeline.test.tsx`

### Context

Copy the pattern from `apps/web/src/app/(dashboard)/plans/[id]/page.tsx` lines 85-210. Each pipeline-item registers as `draggable` + `dropTarget`; each stage-section registers a `monitorForElements` that handles the `onDrop` event, computes the new order with `reorder()`, and calls `useTtsMutations().reorder()`.

Constraint: drag is restricted to the same stage. Encode stage in the drag payload; monitor rejects drops whose source/target stages don't match.

- [ ] **Step 1: Extend the test**

Append to `broadcast-pipeline.test.tsx`:

```tsx
vi.mock('@atlaskit/pragmatic-drag-and-drop/element/adapter', () => ({
  draggable: () => () => {},
  dropTargetForElements: () => () => {},
  monitorForElements: () => () => {},
}))
vi.mock('@atlaskit/pragmatic-drag-and-drop/combine', () => ({ combine: (...fns: Array<() => void>) => () => fns.forEach((f) => f()) }))
vi.mock('@atlaskit/pragmatic-drag-and-drop-hitbox/list-item', () => ({
  attachInstruction: (data: unknown) => data,
  extractInstruction: () => ({ operation: 'reorder-after' }),
}))
vi.mock('@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/list-item', () => ({
  DropIndicator: () => null,
}))
```

(Put those mocks at the top of the file before `describe`.)

No new test assertions needed; the existing 3 tests must continue to pass after the dnd wiring is added.

- [ ] **Step 2: Wire the dnd calls**

The full pattern is >100 lines. Model it verbatim on `plans/[id]/page.tsx`:

In `pipeline-item.tsx`, wrap the card root with refs + `draggable + dropTargetForElements` effects. Drag payload: `{type: 'pipeline-item', stage: item.stage, index}`. Reject drops where `source.data.stage !== self.data.stage`.

In `stage-section.tsx`, mount `monitorForElements`. Filter by `type === 'pipeline-item'` and matching stage. On drop: compute `finishIndex`, call `reorder()` from `@atlaskit/pragmatic-drag-and-drop/reorder`, and invoke `props.onReorder(newIds)`.

In `index.tsx`, hoist a `onReorder(stage, ids)` that calls `useTtsMutations().reorder(stage, ids)`.

Because this task involves direct copy-adaptation from an existing file, DO NOT paste a full code block here — read `plans/[id]/page.tsx` lines 85-210 and adapt them to `pipeline-item` (single card) and `stage-section` (monitor container + onReorder prop).

If you find the adaptation harder than expected (e.g. the existing pattern mixes segment-specific logic with drag logic), STOP and report as DONE_WITH_CONCERNS with a narrower wiring and a follow-up task note.

- [ ] **Step 3: Run — existing tests must still pass**

```bash
pnpm --filter web test broadcast-pipeline
```

Type check + lint.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/live/components/broadcast-pipeline
git commit -m "feat(live): in-stage drag-and-drop for BroadcastPipeline"
```

---

## Task 9: motion layoutId cross-stage animations + wire into live/page.tsx

**Files:**
- Modify: `apps/web/src/features/live/components/broadcast-pipeline/pipeline-item.tsx` — wrap card in `motion.div` with `layoutId={item.id}`
- Modify: `apps/web/src/features/live/components/broadcast-pipeline/index.tsx` — wrap entire stages container in `LayoutGroup` (from `motion/react`) so layoutId transitions across sections
- Modify: `apps/web/src/app/(dashboard)/live/page.tsx` — replace old 3 components with `BroadcastPipeline`, derive `nowPlayingItem` from pipeline
- Modify: `apps/web/src/features/live/hooks/use-live-stream.ts` — add `nowPlayingItem: PipelineItem | null` to return (if not already there; Task 6 of PR 2 added `nowPlaying: AiOutput | null` only)
- Delete: `apps/web/src/features/live/components/ai-status-card.tsx`, `tts-queue-panel.tsx`, `ai-output-log.tsx` + any tests
- Update: `apps/web/src/app/(dashboard)/live/page.test.tsx` — remove mocks for deleted components, add mock for BroadcastPipeline

### Context

motion integration is one-liner per card:

```tsx
import { motion } from 'motion/react'
// ...
<motion.div layoutId={item.id} ...>
```

Wrap the whole pipeline in a `<LayoutGroup>` so the shared layoutId space spans sections. The rest is deletion and rewiring.

- [ ] **Step 1: Update `use-live-stream.ts`**

Add to the return of the hook (find the `return { events, connected, ... }` block):

```ts
  const nowPlayingItem = useMemo(() => pipeline.find((p) => p.stage === 'playing') ?? null, [pipeline])
```

And include in the return object:

```ts
  return {
    events, connected, onlineCount,
    aiOutputs, nowPlaying, nowPlayingItem, ttsQueue, scriptState,
    pending, synthesized, history, pipeline,
  }
```

Also compute `urgentCount`:

```ts
  const urgentCount = useMemo(() => pipeline.filter((p) => p.urgent && (p.stage === 'pending' || p.stage === 'synthesized')).length, [pipeline])
```

And return it. Update `use-live-stream.test.ts` with one new assertion that `urgentCount` is counted correctly — optional but nice.

- [ ] **Step 2: Replace in `live/page.tsx`**

Find the center column block (the `{/* center col */}` section) and replace:

```tsx
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-hidden p-3">
            <div className="shrink-0">
              <AiStatusCard ... />
            </div>
            <div className="shrink-0 rounded-lg border bg-background p-4">
              <TtsQueuePanel ... />
            </div>
            <div className="min-h-0 flex-1">
              <AiOutputLog outputs={aiOutputs} />
            </div>
          </div>
```

With:

```tsx
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-3">
            <BroadcastPipeline
              pending={pending}
              synthesized={synthesized}
              nowPlayingItem={nowPlayingItem}
              history={history}
              llmGenerating={aiSession.state.llm_generating ?? false}
              ttsSpeaking={aiSession.state.tts_speaking ?? false}
              urgentCount={urgentCount}
            />
          </div>
```

Update the `useLiveStream()` destructure:

```ts
  const { events, connected, onlineCount, aiOutputs, nowPlaying, nowPlayingItem, ttsQueue, scriptState, pending, synthesized, history, urgentCount } = useLiveStream()
```

Remove unused imports.

- [ ] **Step 3: Add motion layoutId**

In `pipeline-item.tsx`, import `motion`:

```tsx
import { motion } from 'motion/react'
```

Change the outer `<div>` wrapping the card to `<motion.div layoutId={item.id}>` and keep all props.

In `broadcast-pipeline/index.tsx`, import `LayoutGroup`:

```tsx
import { LayoutGroup } from 'motion/react'
```

Wrap the stages container:

```tsx
      <LayoutGroup>
        <div className="flex min-h-0 flex-1 flex-col overflow-auto">
          <StageSection ... />
          <StageSection ... />
          <NowPlayingCard item={nowPlayingItem} />
          <HistorySection items={history} />
        </div>
      </LayoutGroup>
```

- [ ] **Step 4: Delete old components**

```bash
rm apps/web/src/features/live/components/ai-status-card.tsx
rm apps/web/src/features/live/components/tts-queue-panel.tsx
rm apps/web/src/features/live/components/ai-output-log.tsx
# plus any colocated .test.tsx if they exist
```

Check before deleting:

```bash
ls apps/web/src/features/live/components/ai-*.tsx apps/web/src/features/live/components/tts-*.tsx
```

Delete any `.test.tsx` alongside.

- [ ] **Step 5: Update `live/page.test.tsx`**

Remove the `vi.mock(...)` blocks for the three deleted components. Add:

```tsx
vi.mock('@/features/live/components/broadcast-pipeline', () => ({
  BroadcastPipeline: () => <div data-testid="broadcast-pipeline" />,
}))
```

Remove the test cases that asserted on `ai-status-card` / `tts-queue-panel` / `ai-output-log` props — replace with one case that asserts the pipeline is rendered.

- [ ] **Step 6: Full verify**

```bash
pnpm --filter web test
pnpm --filter web typecheck
pnpm --filter web lint
uv run pytest src/ -q
uv run ruff check src/
```

All green.

Manual e2e (reviewer):

> Start backend + frontend; load plan; start AI broadcast. Verify: (a) pipeline renders 4 sections; (b) delete button on a pending item actually removes it and the server logs show `tts_removed`; (c) edit a pending item via the dialog — text updates in place; (d) edit a synthesized item — confirm dialog warns, then saves; old card fades out, new card appears at pending tail; (e) drag a pending item to a new position; server receives reorder; order persists across reload; (f) no stale pending cards after reconnect (snapshot rehydrate works).

- [ ] **Step 7: Commit**

```bash
git add -A apps/web
git commit -m "feat(live): replace AiStatus/TtsQueue/AiOutputLog with BroadcastPipeline + motion"
```

---

## Task 10: Final cleanup + branch verification

**Files:** none modified

- [ ] **Step 1: Full suite both sides**

```bash
uv run pytest src/ -q
pnpm --filter web test
pnpm --filter web typecheck
pnpm --filter web lint
uv run ruff check src/
```

Expected: all green.

- [ ] **Step 2: Confirm deletions**

```bash
ls apps/web/src/features/live/components/
```

Expected: no `ai-status-card.tsx` / `tts-queue-panel.tsx` / `ai-output-log.tsx`.

- [ ] **Step 3: Commit log**

```bash
git log --oneline master..HEAD
```

Expected: ~35 commits across PR 1 + 2 + 3.

- [ ] **Step 4: Hand off to user for final review + PR creation**

Report back with:
- Total commits
- Line count summary (`git diff --stat master..HEAD | tail -3`)
- Any concerns / known issues

Do NOT push. The user explicitly said: "complete everything first, then PR."

---

## Done criteria

- All mutation helpers + SSE events + REST endpoints + frontend reducer cases covered by unit tests.
- Three legacy components fully removed; `live/page.tsx` renders `BroadcastPipeline` exclusively.
- Drag rearranges items in-stage; cross-stage drag rejected.
- Editing a synthesized item discards PCM and re-enqueues as pending (PR 3 behavior visible in e2e).
- Motion layoutId transitions on stage move; no layout thrash.
- No new ruff / tsc / oxlint errors over master baseline.
