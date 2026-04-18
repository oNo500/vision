# PR 2: tts_synthesized Event + stage Field + Snapshot Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire a new `on_synthesized` callback in `TTSPlayer` and a `tts_synthesized` SSE event in `SessionManager`; add `stage` and `urgent` fields on `TtsItem` / `PcmItem`; widen the `tts_queued` SSE payload and the `get_tts_queue_snapshot` return shape; expose a new `GET /live/tts/queue/snapshot` REST endpoint; rewrite the frontend `useLiveStream` hook to maintain a single `pipeline: PipelineItem[]` array that three adapter views (AiStatusCard, TtsQueuePanel, AiOutputLog) consume without visual change.

**Architecture:** Backend becomes aware of two lifecycle phases (pending → synthesized) and publishes a new event at the transition. Frontend collapses its 4 legacy state fields (`aiOutputs`, `nowPlaying`, `ttsQueue`, plus the implicit queue in `AiStatusCard`) into a single event-driven pipeline. Legacy UI components are kept, each fed from a `useMemo` derived view so UX is untouched while PR 3 can later delete them wholesale.

**Tech Stack:** Python 3.13 (dataclasses, FastAPI, threading), `pytest` + `httpx TestClient`, React 19 + `@t3-oss/env-nextjs`, `vitest` + `@testing-library/react`.

---

## File Map

**Backend modify:**
- `src/live/tts_player.py` — `TtsItem` / `PcmItem` gain `stage` + `urgent` fields; `__init__` accepts a new optional `on_synthesized` callback; `_run_synth` invokes it when PcmItem enters `pcm_queue`
- `src/live/session.py` — publishes `tts_synthesized`; widens `tts_queued` payload; `get_tts_queue_snapshot()` emits `stage` and `urgent` per item; the `_urgent_queue → in_queue` bridge marks the item `urgent=True`
- `src/live/routes.py` — new `GET /live/tts/queue/snapshot` endpoint
- `src/live/routes_test.py` — new test for the snapshot endpoint

**Frontend modify:**
- `apps/web/src/features/live/hooks/use-live-stream.ts` — single `pipeline` state, 5 derived views (`aiOutputs`, `pending`, `synthesized`, `nowPlaying`, `history`), handles 7 event types + one snapshot refill, provides the same return shape as today (backward-compatible)
- `apps/web/src/features/live/hooks/use-live-stream.test.ts` — new vitest suite for the event → state reducer

**No component deletion or visual change in this PR.** Existing `AiStatusCard` / `TtsQueuePanel` / `AiOutputLog` consume the legacy fields through the new derivation layer — deletion happens in PR 3.

---

## Task 1: Add `stage` and `urgent` fields to `TtsItem` / `PcmItem`

**Files:**
- Modify: `src/live/tts_player.py`
- Modify: `src/live/tts_player_test.py` — **note:** this file does not exist; tests for tts_player live under `tests/live/test_tts_player.py`. We will create a new focused test file `src/live/tts_player_item_fields_test.py` colocated with the source per constitution, rather than touch the legacy test file under `tests/live/`.

### Context

The backend currently models `TtsItem(id, text, speech_prompt)`. PR 2 needs two additional read-only fields:

- `stage: Literal["pending", "synthesized"]` — so snapshot consumers know which container an item sits in even after both are concatenated.
- `urgent: bool` — so frontend can render a red badge on items that originated from `urgent_queue` (Orchestrator P0/P1 in `intelligent` strategy → DirectorAgent → `tts_queue` with the urgent flag preserved).

`TtsItem.create()` must default `stage="pending"` + `urgent=False`. Callers that need urgent behaviour override explicitly.

`PcmItem` gets the same two fields. When `_run_synth` converts `TtsItem → PcmItem` it must set `stage="synthesized"` and forward the original `urgent` flag.

- [ ] **Step 1: Write the failing tests**

Create a new file `src/live/tts_player_item_fields_test.py`:

```python
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
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
uv run pytest src/live/tts_player_item_fields_test.py -v
```

Expected: all 4 fail with `TypeError: unexpected keyword argument 'urgent'` (or `AttributeError: 'TtsItem' object has no attribute 'stage'`).

- [ ] **Step 3: Extend the dataclasses**

In `src/live/tts_player.py`:

Replace the existing `TtsItem` dataclass:

```python
@dataclasses.dataclass
class TtsItem:
    id: str
    text: str
    speech_prompt: str | None

    @staticmethod
    def create(text: str, speech_prompt: str | None) -> "TtsItem":
        return TtsItem(id=str(uuid.uuid4()), text=text, speech_prompt=speech_prompt)
```

with:

```python
@dataclasses.dataclass
class TtsItem:
    id: str
    text: str
    speech_prompt: str | None
    stage: str = "pending"       # "pending" | "synthesized"
    urgent: bool = False

    @staticmethod
    def create(text: str, speech_prompt: str | None, urgent: bool = False) -> "TtsItem":
        return TtsItem(
            id=str(uuid.uuid4()),
            text=text,
            speech_prompt=speech_prompt,
            urgent=urgent,
        )
```

Replace the existing `PcmItem`:

```python
@dataclasses.dataclass
class PcmItem:
    id: str
    text: str
    speech_prompt: str | None
    pcm: "np.ndarray"
    duration: float
```

with:

```python
@dataclasses.dataclass
class PcmItem:
    id: str
    text: str
    speech_prompt: str | None
    pcm: "np.ndarray"
    duration: float
    stage: str = "synthesized"
    urgent: bool = False
```

Update the PcmItem construction site inside `_run_synth` (around line 282) to forward `urgent`:

```python
            pcm_item = PcmItem(
                id=item.id,
                text=item.text,
                speech_prompt=item.speech_prompt,
                pcm=pcm,
                duration=duration,
                urgent=item.urgent,
            )
```

- [ ] **Step 4: Run the tests — all must pass**

```bash
uv run pytest src/live/tts_player_item_fields_test.py -v
```

Expected: 4 passed.

Also run the pre-existing live test suite to confirm we didn't break anything:

```bash
uv run pytest src/live/ -q
```

Expected: all still pass (67 + 4 new).

Run ruff on the touched file:

```bash
uv run ruff check src/live/tts_player.py src/live/tts_player_item_fields_test.py
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/live/tts_player.py src/live/tts_player_item_fields_test.py
git commit -m "feat(tts): add stage/urgent fields to TtsItem and PcmItem"
```

---

## Task 2: Wire `on_synthesized` callback in TTSPlayer

**Files:**
- Modify: `src/live/tts_player.py`
- Modify: `src/live/tts_player_item_fields_test.py`

### Context

Today the frontend cannot tell the moment a pending text turns into synthesized PCM — only `tts_queued` (text added) and `tts_playing` (sound starting) exist. Add an optional callback fired from `_run_synth` the moment `pcm_queue.put(pcm_item)` succeeds. This is a pure extension — when the caller doesn't pass a callback, behavior is unchanged.

- [ ] **Step 1: Write the failing test**

Append to `src/live/tts_player_item_fields_test.py`:

```python
import queue
import threading
import time as _time

from src.live.tts_player import TTSPlayer
from src.shared.ordered_item_store import OrderedItemStore


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
```

Note on the first test: the mock path of `TTSPlayer` (when `speak_fn` is set) goes through `_run_mock` which never touches `pcm_queue`. So `on_synthesized` is expected NOT to fire in mock mode. The second test is a pure construction-compat check.

We don't add a test that hits the real Google Cloud synth path because that would require live credentials and network — covered implicitly by the later manual e2e.

- [ ] **Step 2: Run the tests — they must fail**

```bash
uv run pytest src/live/tts_player_item_fields_test.py -v
```

Expected: both new tests fail with `TypeError: TTSPlayer.__init__() got an unexpected keyword argument 'on_synthesized'`.

- [ ] **Step 3: Add the callback parameter and wire it**

In `TTSPlayer.__init__`, add `on_synthesized` alongside the other callbacks:

Find:

```python
        on_queued: Callable[[TtsItem], None] | None = None,
        on_play: Callable[[TtsItem], None] | None = None,
        on_done: Callable[[TtsItem], None] | None = None,
        google_cloud_project: str | None = None,
```

Change to:

```python
        on_queued: Callable[[TtsItem], None] | None = None,
        on_synthesized: Callable[[PcmItem], None] | None = None,
        on_play: Callable[[TtsItem], None] | None = None,
        on_done: Callable[[TtsItem], None] | None = None,
        google_cloud_project: str | None = None,
```

And inside `__init__`:

Find:

```python
        self._on_queued = on_queued
        self._on_play = on_play
        self._on_done = on_done
```

Change to:

```python
        self._on_queued = on_queued
        self._on_synthesized = on_synthesized
        self._on_play = on_play
        self._on_done = on_done
```

Update the docstring `Args` block to mention `on_synthesized`.

In `_run_synth`, fire it right after `pcm_queue.put(pcm_item)` (around line 290):

Find:

```python
            self._queue.task_done()
            self._pcm_queue.put(pcm_item)
```

Change to:

```python
            self._queue.task_done()
            self._pcm_queue.put(pcm_item)
            if self._on_synthesized:
                self._on_synthesized(pcm_item)
```

- [ ] **Step 4: Run the tests — all must pass**

```bash
uv run pytest src/live/tts_player_item_fields_test.py -v
```

Expected: 6 passed total (4 from Task 1 + 2 new).

Run the live suite to ensure no regressions:

```bash
uv run pytest src/live/ -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/live/tts_player.py src/live/tts_player_item_fields_test.py
git commit -m "feat(tts): on_synthesized callback fires when PcmItem enters pcm_queue"
```

---

## Task 3: Publish `tts_synthesized` SSE event and widen `tts_queued` payload

**Files:**
- Modify: `src/live/session.py`
- Modify: `src/live/session_tts_events_test.py` — new test file colocated with source

### Context

`SessionManager._build_and_start` already wires `on_queued / on_play / on_done` into `_bus.publish`. Add a symmetric `_on_synthesized` publisher, and enrich the existing `tts_queued` payload with `stage` and `urgent` fields so the frontend can build a precise lifecycle view.

- [ ] **Step 1: Write the failing tests**

Create `src/live/session_tts_events_test.py`:

```python
"""Tests for SSE events SessionManager publishes when TTS items flow."""
from __future__ import annotations

import time

import pytest

from src.live.tts_player import PcmItem, TtsItem
from src.shared.event_bus import EventBus


@pytest.fixture
def bus_with_collector():
    """Capture every event published to the bus."""
    bus = EventBus()
    collected: list[dict] = []
    bus.subscribe(lambda ev: collected.append(ev))
    return bus, collected


def test_tts_queued_payload_includes_stage_and_urgent(bus_with_collector):
    bus, collected = bus_with_collector
    # Minimal stand-in for the publisher closure inside SessionManager._build_and_start.
    # We call the helper directly to isolate from the full agent lifecycle.
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
    import numpy as np

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
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
uv run pytest src/live/session_tts_events_test.py -v
```

Expected: both fail with `ImportError: cannot import name '_publish_tts_queued'`.

- [ ] **Step 3: Extract publisher helpers in `session.py`**

Keeping the closures inline makes them hard to test. Extract two module-level helpers above `class SessionManager`:

```python
def _publish_tts_queued(bus: EventBus, item: "TtsItem") -> None:
    bus.publish({
        "type": "tts_queued",
        "id": item.id,
        "content": item.text,
        "speech_prompt": item.speech_prompt,
        "stage": item.stage,
        "urgent": item.urgent,
        "ts": time.time(),
    })


def _publish_tts_synthesized(bus: EventBus, item: "PcmItem") -> None:
    bus.publish({
        "type": "tts_synthesized",
        "id": item.id,
        "stage": item.stage,
        "ts": time.time(),
    })
```

Add the import for `PcmItem` alongside the existing `TtsItem` import:

Find:

```python
from src.live.tts_player import TTSPlayer, TtsItem
```

Change to:

```python
from src.live.tts_player import PcmItem, TTSPlayer, TtsItem
```

Then update the closures inside `_build_and_start` to call the helpers:

Find:

```python
        def _on_queued(item: TtsItem) -> None:
            self._bus.publish({
                "type": "tts_queued",
                "id": item.id,
                "content": item.text,
                "speech_prompt": item.speech_prompt,
                "ts": time.time(),
            })

        def _on_play(item: TtsItem) -> None:
```

Replace with:

```python
        def _on_queued(item: TtsItem) -> None:
            _publish_tts_queued(self._bus, item)

        def _on_synthesized(item: PcmItem) -> None:
            _publish_tts_synthesized(self._bus, item)

        def _on_play(item: TtsItem) -> None:
```

And inside the `TTSPlayer(...)` construction call, thread the new callback:

Find (the block around line 295-303):

```python
        tts_player = TTSPlayer(
            tts_queue,
            speak_fn=speak_fn,
            on_queued=_on_queued,
            on_play=_on_play,
            on_done=_on_done,
            google_cloud_project=project,
```

Add `on_synthesized=_on_synthesized,`:

```python
        tts_player = TTSPlayer(
            tts_queue,
            speak_fn=speak_fn,
            on_queued=_on_queued,
            on_synthesized=_on_synthesized,
            on_play=_on_play,
            on_done=_on_done,
            google_cloud_project=project,
```

- [ ] **Step 4: Run the tests — all must pass**

```bash
uv run pytest src/live/session_tts_events_test.py src/live/ -q
```

Expected: both new + all existing session tests pass.

Ruff:

```bash
uv run ruff check src/live/session.py src/live/session_tts_events_test.py
```

Expected: clean for these files (note: `src/live/session.py` may already have pre-existing `UP037` warnings for forward-ref strings in return type annotations — leave those alone).

- [ ] **Step 5: Commit**

```bash
git add src/live/session.py src/live/session_tts_events_test.py
git commit -m "feat(session): publish tts_synthesized event and widen tts_queued payload"
```

---

## Task 4: Widen `get_tts_queue_snapshot` payload and mark urgent items

**Files:**
- Modify: `src/live/session.py`
- Modify: `src/live/session_tts_events_test.py`

### Context

Two changes land together because they touch the same function:

1. Each snapshot item gains `stage` and `urgent` fields (reading them off the dataclass).
2. The `urgent_queue → tts_queue` bridge inside the DirectorAgent path must set `urgent=True` on the TtsItem it constructs, so the snapshot reflects it.

(2) lives in `director_agent.py`; we touch it minimally. Search first to confirm whether the DirectorAgent already constructs TtsItems via `TTSPlayer.put` or via raw `in_queue.put`.

- [ ] **Step 1: Explore where urgent items enter `tts_queue`**

```bash
grep -n "urgent_queue\|urgent\|TtsItem" src/live/director_agent.py src/live/session.py
```

Expected findings: `director_agent.py` drains `urgent_queue` and passes the resulting text to `TTSPlayer.put()`. Confirm the `TTSPlayer.put()` call path and whether it offers a way to mark urgent. If yes, mutate that call. If not, pick the narrowest path to thread `urgent=True` through.

Report findings before writing code. If the path is obvious (single call site), proceed to Step 2. If it requires multi-file refactor, STOP and escalate.

- [ ] **Step 2: Write the failing test for snapshot shape**

Append to `src/live/session_tts_events_test.py`:

```python
def test_tts_queue_snapshot_includes_stage_and_urgent():
    """SessionManager.get_tts_queue_snapshot() returns stage + urgent per item.
    We construct a session-like fixture without touching Google Cloud."""
    from src.live.session import SessionManager

    # We verify the function's shape transformation by stubbing the internal
    # queue + player.snapshot() results. Direct attribute assignment is OK for
    # this unit test — we are not testing start/stop lifecycle.
    bus = EventBus()
    mgr = SessionManager(bus)

    # Simulate a running session with two items straddling the two stages.
    pending = TtsItem.create("pending one", None, urgent=True)
    import numpy as np
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
```

- [ ] **Step 3: Run test — must fail**

```bash
uv run pytest src/live/session_tts_events_test.py::test_tts_queue_snapshot_includes_stage_and_urgent -v
```

Expected: `KeyError: 'stage'` or similar.

- [ ] **Step 4: Update `get_tts_queue_snapshot`**

Find:

```python
        return [
            {"id": item.id, "content": item.text, "speech_prompt": item.speech_prompt}
            for item in all_items
        ]
```

Change to:

```python
        return [
            {
                "id": item.id,
                "content": item.text,
                "speech_prompt": item.speech_prompt,
                "stage": item.stage,
                "urgent": item.urgent,
            }
            for item in all_items
        ]
```

- [ ] **Step 5: Update DirectorAgent urgent path (if Step 1 findings require it)**

If `director_agent.py` constructs TtsItems through `TTSPlayer.put(text, prompt)`, extend the put signature to accept `urgent=False` and pass it to `TtsItem.create(..., urgent=urgent)`. In the DirectorAgent code where urgent events are consumed, set `urgent=True`.

Specifically in `src/live/tts_player.py`, find:

```python
    def put(self, text: str, speech_prompt: str | None) -> TtsItem:
        """Create a TtsItem, fire on_queued, and enqueue it. Returns the item."""
        item = TtsItem.create(text, speech_prompt)
        if self._on_queued:
            self._on_queued(item)
        self._queue.put(item)
        return item
```

Change to:

```python
    def put(self, text: str, speech_prompt: str | None, urgent: bool = False) -> TtsItem:
        """Create a TtsItem, fire on_queued, and enqueue it. Returns the item."""
        item = TtsItem.create(text, speech_prompt, urgent=urgent)
        if self._on_queued:
            self._on_queued(item)
        self._queue.put(item)
        return item
```

Then in `director_agent.py`, find the call site that consumes urgent_queue and calls into TTSPlayer. Add `urgent=True` to that call. (Exact line varies — grep in Step 1 will have located it.)

- [ ] **Step 6: Run full suite**

```bash
uv run pytest src/ -q
```

Expected: all pass.

Ruff:

```bash
uv run ruff check src/live/
```

Expected: no new errors beyond the pre-existing baseline.

- [ ] **Step 7: Commit**

```bash
git add src/live/session.py src/live/tts_player.py src/live/director_agent.py src/live/session_tts_events_test.py
git commit -m "feat(session): snapshot exposes stage/urgent; DirectorAgent flags urgent"
```

---

## Task 5: Add `GET /live/tts/queue/snapshot` REST endpoint

**Files:**
- Modify: `src/live/routes.py`
- Modify: `src/live/routes_test.py`

### Context

The frontend will fetch this endpoint on SSE reconnect to rehydrate its pipeline state from scratch. It returns the same shape as the existing `get_tts_queue_snapshot()` method. No session-started guard — when `_running=False`, returns `[]`.

- [ ] **Step 1: Check current route file structure**

```bash
grep -n "@router\|APIRouter" src/live/routes.py | head -20
```

Expected: existing router + endpoints like `/start`, `/stop`, `/stream`.

- [ ] **Step 2: Write the failing test**

Append to `src/live/routes_test.py`:

```python
def test_tts_queue_snapshot_endpoint_returns_empty_when_not_running(client):
    """When no session is running, snapshot endpoint returns []."""
    response = client.get("/live/tts/queue/snapshot")
    assert response.status_code == 200
    assert response.json() == []


def test_tts_queue_snapshot_endpoint_returns_items_from_session(client, running_session):
    """When a session is running, returns whatever get_tts_queue_snapshot yields."""
    # running_session is an existing fixture — check the file for its definition.
    response = client.get("/live/tts/queue/snapshot")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    for item in body:
        assert "id" in item
        assert "content" in item
        assert "stage" in item
        assert "urgent" in item
```

If `running_session` fixture doesn't exist, adapt the test to the fixture naming used in the rest of `routes_test.py` (check it first with `head -30 src/live/routes_test.py`).

- [ ] **Step 3: Run test — must fail**

```bash
uv run pytest src/live/routes_test.py::test_tts_queue_snapshot_endpoint_returns_empty_when_not_running -v
```

Expected: 404 Not Found.

- [ ] **Step 4: Add the endpoint in `routes.py`**

Find the existing session state endpoint (around line 83):

```python
@router.get("/state")
def get_session_state():
    ...
```

After it, add:

```python
@router.get("/tts/queue/snapshot")
def get_tts_queue_snapshot_endpoint() -> list[dict]:
    """Return a snapshot of pending + synthesized TTS items.

    Used by the frontend to rehydrate pipeline state on SSE reconnect.
    """
    return sm.get_tts_queue_snapshot()
```

(Verify `sm` is the module-level SessionManager instance — grep `sm = ` in the file to confirm the name matches.)

- [ ] **Step 5: Run tests — must pass**

```bash
uv run pytest src/live/routes_test.py -v
```

Expected: all routes tests pass (existing + 2 new).

Full suite:

```bash
uv run pytest src/ -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/live/routes.py src/live/routes_test.py
git commit -m "feat(routes): GET /live/tts/queue/snapshot for frontend reconnect"
```

---

## Task 6: Refactor `useLiveStream` to a single `pipeline` array

**Files:**
- Modify: `apps/web/src/features/live/hooks/use-live-stream.ts`
- Create: `apps/web/src/features/live/hooks/use-live-stream.test.ts`

### Context

Today the hook maintains 4 independent state fields (`aiOutputs`, `nowPlaying`, `ttsQueue`, `events`) updated by independent branches of a switch-like handler. PR 3 will add mutation endpoints that require same-id items to move between stages, so the state model needs to be a single list of items with a `stage` field.

Architecture:
- New internal state: `pipeline: PipelineItem[]`
- 5 derived views via `useMemo` (`aiOutputs`, `pending`, `synthesized`, `nowPlaying`, `history`)
- Return shape: preserve existing fields (`aiOutputs`, `nowPlaying`, `ttsQueue`, `scriptState`, `events`, etc.) by deriving them, so no component outside the hook needs to change
- Add derived fields `pending`, `synthesized`, `history` to the return for PR 3 consumers

`ttsQueue` (legacy) = `pending.concat(synthesized)` — same shape callers see today.
`aiOutputs` (legacy) = `history` — because `aiOutputs` historically was the "played" list.

- [ ] **Step 1: Check how existing components consume the hook**

```bash
grep -rn "useLiveStream\|ttsQueue\|aiOutputs\|nowPlaying" apps/web/src/features/live apps/web/src/app
```

Write down the existing consumers and what fields they read. Your return shape MUST contain all of those fields after refactor (backward compat). No consumer should need modification in this PR.

- [ ] **Step 2: Write the failing test**

Create `apps/web/src/features/live/hooks/use-live-stream.test.ts`:

```ts
/**
 * Unit tests for useLiveStream's event reducer.
 * We extract the reducer into a pure function so we can test it
 * without running a real EventSource.
 */
import { describe, expect, it } from 'vitest'

import { applyLiveEvent, type PipelineItem } from './use-live-stream'

describe('applyLiveEvent', () => {
  it('tts_queued appends a pending item', () => {
    const next = applyLiveEvent([], {
      type: 'tts_queued',
      id: 'a',
      content: 'hi',
      speech_prompt: null,
      stage: 'pending',
      urgent: false,
      ts: 1,
    })
    expect(next).toEqual<PipelineItem[]>([
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
    ])
  })

  it('tts_synthesized promotes the matching id to synthesized', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_synthesized', id: 'a', stage: 'synthesized', ts: 2 })
    expect(next[0].stage).toBe('synthesized')
  })

  it('tts_playing promotes the matching id to playing', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'synthesized', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_playing', id: 'a', content: 'hi', speech_prompt: null, ts: 2 })
    expect(next[0].stage).toBe('playing')
  })

  it('tts_done marks the item done', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'playing', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_done', id: 'a', ts: 3 })
    expect(next[0].stage).toBe('done')
  })

  it('unknown event types are ignored and return the same reference', () => {
    const initial: PipelineItem[] = []
    const next = applyLiveEvent(initial, { type: 'garbage', ts: 0 })
    expect(next).toBe(initial)
  })

  it('tts_synthesized for unknown id is a no-op', () => {
    const initial: PipelineItem[] = []
    const next = applyLiveEvent(initial, { type: 'tts_synthesized', id: 'nope', stage: 'synthesized', ts: 1 })
    expect(next).toBe(initial)
  })
})
```

- [ ] **Step 3: Run test — must fail**

```bash
cd apps/web && pnpm test use-live-stream
```

Expected: import error — `applyLiveEvent` / `PipelineItem` not exported.

- [ ] **Step 4: Refactor the hook**

Open `apps/web/src/features/live/hooks/use-live-stream.ts`.

Add the pipeline types near the top (after existing types):

```ts
export type PipelineStage = 'pending' | 'synthesized' | 'playing' | 'done'

export type PipelineItem = {
  id: string
  content: string
  speech_prompt: string | null
  stage: PipelineStage
  urgent: boolean
  ts: number
}
```

Add the pure reducer as a module-level export (so tests can import it):

```ts
export function applyLiveEvent(prev: PipelineItem[], raw: Record<string, unknown>): PipelineItem[] {
  const type = raw['type'] as string
  const id = raw['id'] as string | undefined

  if (type === 'tts_queued' && id) {
    return [
      ...prev,
      {
        id,
        content: raw['content'] as string,
        speech_prompt: (raw['speech_prompt'] as string | null) ?? null,
        stage: (raw['stage'] as PipelineStage) ?? 'pending',
        urgent: Boolean(raw['urgent']),
        ts: (raw['ts'] as number) ?? Date.now() / 1000,
      },
    ]
  }

  if (type === 'tts_synthesized' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    if (idx < 0) return prev
    const updated = [...prev]
    updated[idx] = { ...updated[idx], stage: 'synthesized' }
    return updated
  }

  if (type === 'tts_playing' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    if (idx < 0) {
      // item wasn't in our view — synthesize a record from the event itself
      return [
        ...prev,
        {
          id,
          content: raw['content'] as string,
          speech_prompt: (raw['speech_prompt'] as string | null) ?? null,
          stage: 'playing',
          urgent: false,
          ts: (raw['ts'] as number) ?? Date.now() / 1000,
        },
      ]
    }
    const updated = [...prev]
    updated[idx] = { ...updated[idx], stage: 'playing' }
    return updated
  }

  if (type === 'tts_done' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    if (idx < 0) return prev
    const updated = [...prev]
    updated[idx] = { ...updated[idx], stage: 'done' }
    return updated
  }

  return prev
}
```

Inside the hook body, replace the four state fields with one:

Find:

```ts
  const [aiOutputs, setAiOutputs] = useState<AiOutput[]>([])
  const [nowPlaying, setNowPlaying] = useState<AiOutput | null>(null)
  const [ttsQueue, setTtsQueue] = useState<TtsQueueItem[]>([])
```

Replace with:

```ts
  const [pipeline, setPipeline] = useState<PipelineItem[]>([])
```

Within `es.onmessage`, replace the separate `tts_queued` / `tts_playing` / `tts_done` branches with a single dispatch. Keep the non-TTS branches (`stats`, `script`, `ping`, `agent`, interaction events) untouched.

Find this block:

```ts
        if (type === 'tts_output') { ... }
        if (type === 'tts_playing') { ... }
        if (type === 'tts_queued') { ... }
        if (type === 'tts_done') { ... }
```

Replace with:

```ts
        if (type === 'tts_output') {
          // legacy: treated as "AI produced text" — keep feeding aiOutputs cache
          // for backward compat with components that cache on reload
          const output: AiOutput = {
            content: raw['content'] as string,
            source: raw['source'] as AiOutput['source'],
            speech_prompt: (raw['speech_prompt'] as string) ?? '',
            ts: raw['ts'] as number,
          }
          // Note: aiOutputs cache is now derived from pipeline (see useMemo below);
          // but we still persist it to sessionStorage for reload resilience
          setPipeline((prev) => applyLiveEvent(prev, {
            type: 'tts_queued',
            id: `output-${output.ts}`,
            content: output.content,
            speech_prompt: output.speech_prompt || null,
            stage: 'pending',
            urgent: false,
            ts: output.ts,
          }))
          return
        }

        if (type === 'tts_queued' || type === 'tts_synthesized' || type === 'tts_playing' || type === 'tts_done') {
          setPipeline((prev) => applyLiveEvent(prev, raw))
          return
        }
```

(Note: the `tts_output` branch now feeds the pipeline too — it was the legacy event used before `tts_queued` existed. If grep in Step 1 shows `tts_output` is still produced by the backend, keep this; if grep shows it's only legacy, drop the branch. Confirm before writing.)

Add the derived views with `useMemo`:

```ts
  const pending = useMemo(() => pipeline.filter((p) => p.stage === 'pending'), [pipeline])
  const synthesized = useMemo(() => pipeline.filter((p) => p.stage === 'synthesized'), [pipeline])
  const nowPlaying = useMemo<AiOutput | null>(() => {
    const found = pipeline.find((p) => p.stage === 'playing')
    return found
      ? { content: found.content, source: 'agent', speech_prompt: found.speech_prompt ?? '', ts: found.ts }
      : null
  }, [pipeline])
  const history = useMemo(
    () => pipeline.filter((p) => p.stage === 'done').slice(-MAX_EVENTS),
    [pipeline],
  )
  // Backward-compat aliases for existing consumers
  const aiOutputs = useMemo<AiOutput[]>(
    () => history.map((p) => ({
      content: p.content,
      source: 'agent' as const,
      speech_prompt: p.speech_prompt ?? '',
      ts: p.ts,
    })),
    [history],
  )
  const ttsQueue = useMemo<TtsQueueItem[]>(
    () => [...pending, ...synthesized].map((p) => ({
      id: p.id,
      content: p.content,
      speech_prompt: p.speech_prompt,
    })),
    [pending, synthesized],
  )
```

Update the return:

```ts
  return {
    events, connected, onlineCount,
    aiOutputs, nowPlaying, ttsQueue, scriptState,
    pending, synthesized, history, pipeline,
  }
```

On SSE reconnect, rehydrate from the snapshot endpoint. Find the existing teardown in the `useEffect`:

```ts
    return () => {
      es.close()
      esRef.current = null
      setConnected(false)
      setTtsQueue([])
      setNowPlaying(null)
    }
```

Change to:

```ts
    return () => {
      es.close()
      esRef.current = null
      setConnected(false)
      setPipeline((prev) => prev.filter((p) => p.stage === 'done'))  // keep history, drop in-flight
    }
```

And add a rehydrate call inside `es.onopen`:

Find:

```ts
    es.onopen = () => setConnected(true)
```

Change to:

```ts
    es.onopen = async () => {
      setConnected(true)
      try {
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/snapshot`)
        if (res.ok) {
          const snap = (await res.json()) as Array<{
            id: string
            content: string
            speech_prompt: string | null
            stage: PipelineStage
            urgent: boolean
          }>
          setPipeline((prev) => {
            // preserve local 'playing' / 'done' items the server doesn't know about
            const keep = prev.filter((p) => p.stage === 'playing' || p.stage === 'done')
            const fresh: PipelineItem[] = snap.map((s) => ({
              id: s.id,
              content: s.content,
              speech_prompt: s.speech_prompt,
              stage: s.stage,
              urgent: s.urgent,
              ts: Date.now() / 1000,
            }))
            return [...keep, ...fresh]
          })
        }
      } catch {
        // ignore snapshot fetch failure; SSE events will eventually catch up
      }
    }
```

Add the missing imports (`useMemo`) at the top:

```ts
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
```

- [ ] **Step 5: Run tests — must pass**

```bash
cd apps/web && pnpm test use-live-stream
```

Expected: 6 passed.

Type check:

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/features/live/hooks/use-live-stream.ts apps/web/src/features/live/hooks/use-live-stream.test.ts
git commit -m "refactor(live): useLiveStream maintains unified pipeline state"
```

---

## Task 7: Final verification and branch prep

**Files:** none modified

### Context

Validate the full stack and confirm no behavioral drift.

- [ ] **Step 1: Backend full suite**

```bash
uv run pytest src/ -q
```

Expected: all green. (The `tests/live/` 9 pre-existing failures are tracked against master — note them if they appear but do not block.)

- [ ] **Step 2: Backend lint**

```bash
uv run ruff check src/
```

Expected: no new errors beyond master baseline. Count the pre-existing ones for comparison.

- [ ] **Step 3: Frontend lint + type check**

```bash
cd apps/web && pnpm lint && pnpm exec tsc --noEmit
```

Expected: clean.

- [ ] **Step 4: Frontend tests**

```bash
cd apps/web && pnpm test
```

Expected: all green (new `use-live-stream.test.ts` + existing).

- [ ] **Step 5: Manual e2e smoke test**

Hand off to the reviewer:

> "Please start the backend (`uv run uvicorn src.api.main:app --host 127.0.0.1 --port 8000`) + frontend (`pnpm --filter web dev`), load a demo plan, click 启动 AI 主播, and verify: (a) TTS plays cleanly, (b) in DevTools Network tab you see one `GET /live/tts/queue/snapshot` fire on page load, (c) the Live EventStream shows `tts_synthesized` events arriving between `tts_queued` and `tts_playing`, (d) no visual change to AiStatusCard / TtsQueuePanel / AiOutputLog — they render the same as on master."

- [ ] **Step 6: Review commit log**

```bash
git log --oneline master..HEAD
```

Expected: 6-7 new commits for PR 2 tasks stacked above PR 1 commits.

---

## Done criteria

- 6+ new backend tests pass (`tts_player_item_fields_test.py`, `session_tts_events_test.py`, `routes_test.py`).
- 6 new frontend reducer tests pass (`use-live-stream.test.ts`).
- `grep -n "tts_synthesized" src/live/session.py src/live/tts_player.py` shows the event wiring in both places.
- `curl http://localhost:8000/live/tts/queue/snapshot` returns an array shape (200 when running, `[]` when not).
- Existing UI components render identically — no visual change.
