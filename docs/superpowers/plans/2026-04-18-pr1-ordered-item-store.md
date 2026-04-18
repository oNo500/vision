# PR 1: OrderedItemStore + tts_player Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `queue.Queue` inside `TTSPlayer` with a new thread-safe `OrderedItemStore[T]` that exposes the same Queue-compatible producer/consumer API plus future mutation-by-UUID hooks, without changing any user-visible behavior.

**Architecture:** Introduce a generic ordered container in `src/shared/ordered_item_store.py` backed by a `list` + `dict[id → item]`, protected by a single `threading.Lock` paired with two `Condition` variables (not-empty for blocked consumers, not-full for blocked producers). Swap both `queue.Queue` instances inside `TTSPlayer` (the in-queue and the internal `_pcm_queue`) over to it. All existing callers keep working because the new container exposes `put` / `get` / `qsize` / `task_done` with matching semantics.

**Tech Stack:** Python 3.13, `threading` (Lock/Condition), `pytest`, existing `TTSPlayer` + `SessionManager` modules.

---

## File Map

**Create:**
- `src/shared/ordered_item_store.py` — the new generic container
- `src/shared/ordered_item_store_test.py` — unit + concurrency tests

**Modify:**
- `src/live/tts_player.py`
  - Replace `queue.Queue` type hints / instantiation with `OrderedItemStore`
  - Keep all producer/consumer logic byte-identical
  - Adapt `stop()` sentinel path (the new container's `get()` returns an object the same way)
- `src/live/session.py`
  - `get_tts_queue_snapshot()` uses the new `.snapshot()` method instead of poking `.queue` internals

**No API or SSE event changes in this PR.**

---

## Task 1: Scaffold `OrderedItemStore` with the Queue-compatible surface

**Files:**
- Create: `src/shared/ordered_item_store.py`
- Create: `src/shared/ordered_item_store_test.py`

### Context

The new container must be a drop-in replacement for `queue.Queue` for producer/consumer threads. We implement the core API first (`put`, `get`, `qsize`, `task_done`) so the rest of the codebase can swap in later without refactoring consumer loops.

Key decisions:
- Internal representation: `list[T]` (order of insertion) + `dict[str, T]` (id → item index for O(1) lookup later). In this task we only use the list; the dict lands in Task 3.
- Locking: one `threading.Lock`, one `threading.Condition` bound to it for blocked consumers (`_not_empty`) and one for blocked producers when `maxsize` is set (`_not_full`).
- `get(timeout=None)` blocks until an item is available OR timeout expires. On timeout raises `queue.Empty` (so callers that catch `queue.Empty` continue to work).
- `put(item, block=True, timeout=None)` respects `maxsize` the same way `queue.Queue` does. On `maxsize` violation with `block=False` raises `queue.Full`.
- `task_done()` is a no-op placeholder (we don't track outstanding tasks; existing tts_player calls it but nothing else depends on `join()`).
- Items must expose an `id: str` attribute — we don't enforce it at the type level (plain dataclass check in `put`) so the container is reusable; tests assert the requirement.

- [ ] **Step 1: Write the failing tests**

```python
# src/shared/ordered_item_store_test.py
"""Tests for OrderedItemStore — Queue-compatible core API."""
from __future__ import annotations

import dataclasses
import queue
import threading
import time

import pytest

from src.shared.ordered_item_store import OrderedItemStore


@dataclasses.dataclass
class _Item:
    id: str
    value: int


def test_put_then_get_returns_same_item():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    item = _Item(id="a", value=1)
    store.put(item)
    assert store.get(timeout=1) is item


def test_get_empty_times_out():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    with pytest.raises(queue.Empty):
        store.get(timeout=0.05)


def test_qsize_reflects_contents():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    assert store.qsize() == 0
    store.put(_Item(id="a", value=1))
    store.put(_Item(id="b", value=2))
    assert store.qsize() == 2
    store.get(timeout=1)
    assert store.qsize() == 1


def test_get_returns_fifo_order():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    for i in range(5):
        store.put(_Item(id=f"i{i}", value=i))
    got = [store.get(timeout=1).value for _ in range(5)]
    assert got == [0, 1, 2, 3, 4]


def test_put_blocks_when_maxsize_full_and_unblocks_on_get():
    store: OrderedItemStore[_Item] = OrderedItemStore(maxsize=2)
    store.put(_Item(id="a", value=1))
    store.put(_Item(id="b", value=2))

    put_done = threading.Event()

    def _producer():
        store.put(_Item(id="c", value=3))
        put_done.set()

    threading.Thread(target=_producer, daemon=True).start()
    assert not put_done.wait(timeout=0.1)  # blocked

    store.get(timeout=1)
    assert put_done.wait(timeout=1)  # unblocked after consume


def test_put_nowait_raises_when_full():
    store: OrderedItemStore[_Item] = OrderedItemStore(maxsize=1)
    store.put(_Item(id="a", value=1))
    with pytest.raises(queue.Full):
        store.put(_Item(id="b", value=2), block=False)


def test_get_blocks_until_put_from_another_thread():
    store: OrderedItemStore[_Item] = OrderedItemStore()

    got: list[_Item] = []

    def _consumer():
        got.append(store.get(timeout=2))

    t = threading.Thread(target=_consumer, daemon=True)
    t.start()
    time.sleep(0.05)  # let consumer enter wait
    store.put(_Item(id="x", value=42))
    t.join(timeout=2)

    assert len(got) == 1 and got[0].value == 42


def test_task_done_is_callable():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    store.put(_Item(id="a", value=1))
    store.get(timeout=1)
    store.task_done()  # no-op, must not raise
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
uv run pytest src/shared/ordered_item_store_test.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.shared.ordered_item_store'`

- [ ] **Step 3: Implement the minimal container**

```python
# src/shared/ordered_item_store.py
"""Thread-safe ordered container — a Queue-compatible replacement that also
supports future mutation-by-id operations (remove / move / edit).

Producer/consumer API mirrors `queue.Queue` so existing consumer loops keep
working. Items must expose an `id: str` attribute; we rely on that for the
id-based mutations added later.
"""
from __future__ import annotations

import queue
import threading
from typing import Generic, Protocol, TypeVar


class _HasId(Protocol):
    id: str


T = TypeVar("T", bound=_HasId)


class OrderedItemStore(Generic[T]):
    """List-backed queue with optional maxsize and blocking get/put."""

    def __init__(self, maxsize: int = 0) -> None:
        self._maxsize = maxsize
        self._items: list[T] = []
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)

    # ----- Queue-compatible API -----

    def qsize(self) -> int:
        with self._lock:
            return len(self._items)

    def put(self, item: T, block: bool = True, timeout: float | None = None) -> None:
        with self._not_full:
            if self._maxsize > 0:
                if not block:
                    if len(self._items) >= self._maxsize:
                        raise queue.Full
                elif timeout is None:
                    while len(self._items) >= self._maxsize:
                        self._not_full.wait()
                else:
                    import time as _time
                    deadline = _time.monotonic() + timeout
                    while len(self._items) >= self._maxsize:
                        remaining = deadline - _time.monotonic()
                        if remaining <= 0:
                            raise queue.Full
                        self._not_full.wait(timeout=remaining)
            self._items.append(item)
            self._not_empty.notify()

    def put_nowait(self, item: T) -> None:
        self.put(item, block=False)

    def get(self, block: bool = True, timeout: float | None = None) -> T:
        with self._not_empty:
            if not block:
                if not self._items:
                    raise queue.Empty
            elif timeout is None:
                while not self._items:
                    self._not_empty.wait()
            else:
                import time as _time
                deadline = _time.monotonic() + timeout
                while not self._items:
                    remaining = deadline - _time.monotonic()
                    if remaining <= 0:
                        raise queue.Empty
                    self._not_empty.wait(timeout=remaining)
            item = self._items.pop(0)
            self._not_full.notify()
            return item

    def get_nowait(self) -> T:
        return self.get(block=False)

    def task_done(self) -> None:
        """No-op. Present for queue.Queue compatibility; we don't track joins."""
        return None
```

- [ ] **Step 4: Run the tests — all must pass**

```bash
uv run pytest src/shared/ordered_item_store_test.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shared/ordered_item_store.py src/shared/ordered_item_store_test.py
git commit -m "feat(shared): OrderedItemStore core queue-compatible API"
```

---

## Task 2: Add `snapshot()` read-only view

**Files:**
- Modify: `src/shared/ordered_item_store.py`
- Modify: `src/shared/ordered_item_store_test.py`

### Context

`SessionManager.get_tts_queue_snapshot()` currently reaches into `queue.Queue.queue` (the private deque) to enumerate items. That is fragile; the new container exposes a safe `.snapshot()` returning a list copy. The copy is taken under the lock so concurrent writers can't mutate mid-iteration.

- [ ] **Step 1: Write the failing test**

Append to `src/shared/ordered_item_store_test.py`:

```python
def test_snapshot_returns_items_in_order_without_mutating_store():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    items = [_Item(id=f"i{i}", value=i) for i in range(3)]
    for it in items:
        store.put(it)

    snap = store.snapshot()
    assert snap == items  # same order, same objects
    assert snap is not store._items  # copy, not alias
    assert store.qsize() == 3  # not consumed
```

- [ ] **Step 2: Run the test — it must fail**

```bash
uv run pytest src/shared/ordered_item_store_test.py::test_snapshot_returns_items_in_order_without_mutating_store -v
```

Expected: `AttributeError: 'OrderedItemStore' object has no attribute 'snapshot'`

- [ ] **Step 3: Implement `snapshot()`**

Add to `OrderedItemStore`:

```python
    def snapshot(self) -> list[T]:
        """Return a shallow copy of current items in order. Thread-safe."""
        with self._lock:
            return list(self._items)
```

- [ ] **Step 4: Run the full file — all pass**

```bash
uv run pytest src/shared/ordered_item_store_test.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shared/ordered_item_store.py src/shared/ordered_item_store_test.py
git commit -m "feat(shared): OrderedItemStore.snapshot for safe iteration"
```

---

## Task 3: Add id-based mutations (`remove`, `move`, `edit`) with concurrency test

**Files:**
- Modify: `src/shared/ordered_item_store.py`
- Modify: `src/shared/ordered_item_store_test.py`

### Context

These methods aren't called yet in this PR, but we land them here so the container's thread-safety story is complete in one place. PR 2 and PR 3 will call them.

- `remove(id)` → `T | None`. Returns the removed item if found, or `None`. On success notifies `_not_full` so a blocked producer wakes up.
- `move(id, to_index)` → `bool`. Moves the matching item to the new index (0-based, clamped to valid range). Returns `True` if found.
- `edit(id, mutator)` → `bool`. Calls `mutator(item)` which returns the replacement item (must keep the same id). Returns `True` if found.

All three take the same lock as put/get to guarantee isolation.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_remove_deletes_item_by_id_and_returns_it():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    a = _Item(id="a", value=1)
    b = _Item(id="b", value=2)
    store.put(a)
    store.put(b)

    removed = store.remove("a")
    assert removed is a
    assert [it.id for it in store.snapshot()] == ["b"]


def test_remove_returns_none_when_id_missing():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    store.put(_Item(id="a", value=1))
    assert store.remove("missing") is None
    assert store.qsize() == 1


def test_remove_unblocks_blocked_producer_when_maxsize_hit():
    store: OrderedItemStore[_Item] = OrderedItemStore(maxsize=1)
    store.put(_Item(id="a", value=1))

    put_done = threading.Event()

    def _producer():
        store.put(_Item(id="b", value=2))
        put_done.set()

    threading.Thread(target=_producer, daemon=True).start()
    assert not put_done.wait(timeout=0.1)  # producer is blocked

    assert store.remove("a") is not None
    assert put_done.wait(timeout=1)


def test_move_reorders_item_to_new_index():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    for i in range(4):
        store.put(_Item(id=f"i{i}", value=i))

    assert store.move("i3", 0) is True
    assert [it.id for it in store.snapshot()] == ["i3", "i0", "i1", "i2"]


def test_move_returns_false_when_id_missing():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    store.put(_Item(id="a", value=1))
    assert store.move("nope", 0) is False


def test_edit_replaces_item_with_mutator_result():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    store.put(_Item(id="a", value=1))

    def _bump(old: _Item) -> _Item:
        return _Item(id=old.id, value=old.value + 100)

    assert store.edit("a", _bump) is True
    assert store.snapshot()[0].value == 101


def test_edit_returns_false_when_id_missing():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    assert store.edit("missing", lambda it: it) is False


def test_concurrent_put_get_and_remove_converges_to_consistent_state():
    """10 producers + 5 consumers + 5 removers — final id set must be
    (produced_ids - consumed_ids - removed_ids)."""
    store: OrderedItemStore[_Item] = OrderedItemStore()
    produced_ids: list[str] = []
    consumed_ids: list[str] = []
    removed_ids: list[str] = []

    stop = threading.Event()

    def _producer(n: int):
        for i in range(50):
            item = _Item(id=f"p{n}-{i}", value=i)
            produced_ids.append(item.id)
            store.put(item)

    def _consumer():
        while not stop.is_set():
            try:
                it = store.get(timeout=0.05)
            except queue.Empty:
                continue
            consumed_ids.append(it.id)

    def _remover():
        while not stop.is_set():
            snap = store.snapshot()
            if snap:
                victim = snap[0].id
                if store.remove(victim) is not None:
                    removed_ids.append(victim)
            else:
                time.sleep(0.01)

    threads: list[threading.Thread] = []
    for i in range(10):
        t = threading.Thread(target=_producer, args=(i,), daemon=True)
        t.start()
        threads.append(t)
    for _ in range(5):
        t = threading.Thread(target=_consumer, daemon=True)
        t.start()
        threads.append(t)
    for _ in range(5):
        t = threading.Thread(target=_remover, daemon=True)
        t.start()
        threads.append(t)

    for t in threads[:10]:  # wait for producers to finish
        t.join(timeout=5)

    # drain: give consumers+removers a moment to clear
    time.sleep(0.5)
    stop.set()
    for t in threads[10:]:
        t.join(timeout=1)

    remaining_ids = {it.id for it in store.snapshot()}
    assert len(produced_ids) == 500
    # every produced id is accounted for exactly once
    accounted = set(consumed_ids) | set(removed_ids) | remaining_ids
    assert accounted == set(produced_ids)
    # no double-counting
    assert len(consumed_ids) + len(removed_ids) + len(remaining_ids) == 500
```

- [ ] **Step 2: Run the new tests — they must fail**

```bash
uv run pytest src/shared/ordered_item_store_test.py -v
```

Expected: the 7 new tests fail with `AttributeError`; the concurrency test fails likewise.

- [ ] **Step 3: Implement the three mutators**

Add to `OrderedItemStore`:

```python
    def remove(self, item_id: str) -> T | None:
        with self._lock:
            for i, it in enumerate(self._items):
                if it.id == item_id:
                    removed = self._items.pop(i)
                    self._not_full.notify()
                    return removed
            return None

    def move(self, item_id: str, to_index: int) -> bool:
        with self._lock:
            for i, it in enumerate(self._items):
                if it.id == item_id:
                    self._items.pop(i)
                    idx = max(0, min(to_index, len(self._items)))
                    self._items.insert(idx, it)
                    return True
            return False

    def edit(self, item_id: str, mutator: "Callable[[T], T]") -> bool:
        with self._lock:
            for i, it in enumerate(self._items):
                if it.id == item_id:
                    self._items[i] = mutator(it)
                    return True
            return False
```

And add the import at the top of the file:

```python
from collections.abc import Callable
```

- [ ] **Step 4: Run the full test file — all pass**

```bash
uv run pytest src/shared/ordered_item_store_test.py -v
```

Expected: 16 passed. (The concurrency test may take ~1s; that's fine.)

- [ ] **Step 5: Commit**

```bash
git add src/shared/ordered_item_store.py src/shared/ordered_item_store_test.py
git commit -m "feat(shared): OrderedItemStore remove/move/edit by id + concurrency test"
```

---

## Task 4: Swap `TTSPlayer` internal `_pcm_queue` to `OrderedItemStore`

**Files:**
- Modify: `src/live/tts_player.py`

### Context

`_pcm_queue` is the easier of the two to swap because it's an internal attribute — no other module reaches into it. We change the type annotation and constructor call; the rest of the code uses only `put` / `get` / `put_nowait` / `task_done` / `qsize`, all of which the new container supports identically.

Note: `_SENTINEL` is a bare `object()` and does NOT have an `id` attribute. The protocol annotation uses `Protocol`, so at runtime nothing actually checks for `id` presence — the sentinel still flows through. That's intentional and matches `queue.Queue`'s duck typing.

- [ ] **Step 1: Read current state of `tts_player.py` lines 91-103 to confirm structure**

```bash
sed -n '91,103p' src/live/tts_player.py
```

Expected to see `self._queue = in_queue`, `self._pcm_queue: queue.Queue = queue.Queue(maxsize=10)`.

- [ ] **Step 2: Change the `_pcm_queue` type and constructor**

Replace:

```python
        self._pcm_queue: queue.Queue = queue.Queue(maxsize=10)
```

With:

```python
        self._pcm_queue: OrderedItemStore = OrderedItemStore(maxsize=10)
```

Add import at the top (after the existing `import queue`):

```python
from src.shared.ordered_item_store import OrderedItemStore
```

- [ ] **Step 3: Run existing tts/session tests**

```bash
uv run pytest src/live/ -v -x
```

Expected: all existing tests pass. If any test reaches into `self._pcm_queue.queue` (the old deque), update the test to use `.snapshot()` in Task 6.

- [ ] **Step 4: Smoke-check stop() sentinel path**

Read lines 158-173. `put_nowait(_SENTINEL)` must still work even though `_SENTINEL` has no `.id`. Because we only check ids inside `remove` / `move` / `edit`, and `stop()` only calls `put_nowait` / `get`, the sentinel continues to flow through. Do not change `stop()`.

- [ ] **Step 5: Commit**

```bash
git add src/live/tts_player.py
git commit -m "refactor(tts): swap internal pcm queue to OrderedItemStore"
```

---

## Task 5: Swap `TTSPlayer` external `in_queue` parameter type

**Files:**
- Modify: `src/live/tts_player.py`
- Modify: `src/live/session.py`

### Context

The in-queue is constructed by `SessionManager._build_and_start` and passed into `TTSPlayer`. Two call sites must change: the construction site (session.py line 206) and the parameter type on `TTSPlayer.__init__`.

Nothing else consumes it — the danmaku manager and director agent take it as a plain `queue.Queue` type hint but only call `.put()`, which is API-identical.

- [ ] **Step 1: Update `TTSPlayer.__init__` parameter type**

Current (tts_player.py around line 81-90):

```python
    def __init__(
        self,
        in_queue: queue.Queue,
        ...
```

Change to:

```python
    def __init__(
        self,
        in_queue: OrderedItemStore,
        ...
```

- [ ] **Step 2: Update `SessionManager._build_and_start` to construct an `OrderedItemStore`**

Find in `src/live/session.py`:

```python
        tts_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
```

Replace with:

```python
        from src.live.tts_player import TtsItem  # already imported below but keep local for clarity
        tts_queue: OrderedItemStore[TtsItem] = OrderedItemStore()
```

And add to session.py imports (alongside existing `import queue`):

```python
from src.shared.ordered_item_store import OrderedItemStore
```

Also update the annotated field on `SessionManager`:

Find:

```python
        self._tts_queue: queue.Queue | None = None
```

Change to:

```python
        self._tts_queue: OrderedItemStore | None = None
```

And the getter `get_tts_queue`:

```python
    def get_tts_queue(self) -> "queue.Queue | None":
        ...
```

Change return annotation to:

```python
    def get_tts_queue(self) -> "OrderedItemStore | None":
        ...
```

- [ ] **Step 3: Check remaining `queue.Queue` hints in `session.py`**

Search: `grep -n "queue.Queue\|queue\.Empty\|queue\.Full" src/live/session.py`

The `urgent_queue` still uses `queue.Queue(maxsize=10)` — **leave that alone** in this PR. It's consumed by `DanmakuManager` directly with Queue semantics and we're not refactoring that flow. PR 2 will reconsider.

- [ ] **Step 4: Run all live tests**

```bash
uv run pytest src/live/ -v -x
```

Expected: all pass. If a test uses `queue.Queue()` for a fixture and passes it to TTSPlayer, update the fixture to `OrderedItemStore()`.

- [ ] **Step 5: Commit**

```bash
git add src/live/tts_player.py src/live/session.py
git commit -m "refactor(tts): accept OrderedItemStore as in_queue parameter"
```

---

## Task 6: Replace `get_tts_queue_snapshot` internals

**Files:**
- Modify: `src/live/session.py`

### Context

Currently `get_tts_queue_snapshot` pokes `q.queue` (the private deque) and `player._pcm_queue.queue`. With the new container we have a public `.snapshot()` — use it. Payload shape is unchanged in this PR (PR 2 will add `stage` / `urgent`).

- [ ] **Step 1: Locate the current implementation**

Read `src/live/session.py` around line 152-171.

Expected current body:

```python
        text_items = [i for i in list(q.queue) if isinstance(i, TtsItem)]
        pcm_items = [i for i in list(player._pcm_queue.queue) if hasattr(i, "id")]
```

- [ ] **Step 2: Replace with `.snapshot()` calls**

```python
        text_items = [i for i in q.snapshot() if isinstance(i, TtsItem)]
        pcm_items = [i for i in player._pcm_queue.snapshot() if hasattr(i, "id")]
```

(The `isinstance` / `hasattr` filters guard against the `_SENTINEL` object that may briefly appear during `stop()`.)

- [ ] **Step 3: Run the full suite**

```bash
uv run pytest src/live/ src/shared/ -v
```

Expected: all pass.

- [ ] **Step 4: Manual e2e smoke test (reviewer instruction)**

This step is a manual verification. The agent should tell the reviewer:

> "Please start the backend (`uv run uvicorn src.api.main:app --host 127.0.0.1 --port 8000`) and the frontend (`pnpm --filter web dev`), load the demo plan, click 启动 on AI 主播, and listen for ~30 seconds. Verify: (a) TTS plays without pops/clicks, (b) 队列 / 紧急 counters update normally, (c) 待播队列 panel shows pending and synthesized items together. No audible or visual change expected versus master."

- [ ] **Step 5: Commit**

```bash
git add src/live/session.py
git commit -m "refactor(session): use OrderedItemStore.snapshot for tts queue view"
```

---

## Task 7: Final verification and PR prep

**Files:** none modified

### Context

Make sure nothing regresses, the diff looks clean, and all commits are present.

- [ ] **Step 1: Full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Lint**

```bash
uv run ruff check src/
```

Expected: no errors.

- [ ] **Step 3: Grep for leftover `queue.Queue` references inside `tts_player` / `session`**

```bash
grep -n "queue\.Queue" src/live/tts_player.py src/live/session.py
```

Expected output:
- `src/live/session.py: urgent_queue: queue.Queue = queue.Queue(maxsize=10)` (intentional, stays in this PR)
- Nothing else.

- [ ] **Step 4: Review commit log**

```bash
git log --oneline master..HEAD
```

Expected: 6 commits with messages:
1. `feat(shared): OrderedItemStore core queue-compatible API`
2. `feat(shared): OrderedItemStore.snapshot for safe iteration`
3. `feat(shared): OrderedItemStore remove/move/edit by id + concurrency test`
4. `refactor(tts): swap internal pcm queue to OrderedItemStore`
5. `refactor(tts): accept OrderedItemStore as in_queue parameter`
6. `refactor(session): use OrderedItemStore.snapshot for tts queue view`

- [ ] **Step 5: Push + open PR (if running with push authorization)**

```bash
git push -u origin <branch-name>
gh pr create --title "refactor(tts): OrderedItemStore replaces queue.Queue in TTSPlayer" --body "$(cat <<'EOF'
## Summary
- Introduces `src/shared/ordered_item_store.py`: a thread-safe, queue-compatible ordered container with future mutation hooks (`remove` / `move` / `edit`).
- Swaps both `queue.Queue` instances inside `TTSPlayer` (in-queue + pcm-queue) over to it.
- Replaces `get_tts_queue_snapshot` internals to use the safe `.snapshot()` instead of poking `.queue`.
- No user-visible change, no API / SSE change. `urgent_queue` intentionally unchanged in this PR.

Part of the TTS pipeline refactor (see `docs/superpowers/specs/2026-04-18-tts-pipeline-refactor-design.md`, PR 1 of 3).

## Test plan
- [ ] `uv run pytest` — all pass
- [ ] `uv run ruff check src/` — clean
- [ ] Manual e2e: start backend + frontend + demo plan, verify AI broadcast plays 30s without pops and UI counters behave normally.
EOF
)"
```

If not authorized to push, stop after Step 4 and hand off.

---

## Done criteria

- All 16 new unit/concurrency tests pass.
- All pre-existing `src/live/` tests still pass.
- `grep "queue\\.Queue" src/live/tts_player.py` returns only `import queue` / `queue.Empty` / `queue.Full` references — no `queue.Queue(` constructors.
- Manual e2e smoke test confirms no audible or visual change.
