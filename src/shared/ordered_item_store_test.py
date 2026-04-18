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
    ready = threading.Event()

    def _consumer():
        ready.set()
        got.append(store.get(timeout=2))

    t = threading.Thread(target=_consumer, daemon=True)
    t.start()
    ready.wait(timeout=1)
    store.put(_Item(id="x", value=42))
    t.join(timeout=2)

    assert len(got) == 1 and got[0].value == 42


def test_task_done_is_callable():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    store.put(_Item(id="a", value=1))
    store.get(timeout=1)
    store.task_done()  # no-op, must not raise


def test_put_full_times_out():
    store: OrderedItemStore[_Item] = OrderedItemStore(maxsize=1)
    store.put(_Item(id="a", value=1))
    with pytest.raises(queue.Full):
        store.put(_Item(id="b", value=2), timeout=0.05)


def test_snapshot_returns_items_in_order_without_mutating_store():
    store: OrderedItemStore[_Item] = OrderedItemStore()
    items = [_Item(id=f"i{i}", value=i) for i in range(3)]
    for it in items:
        store.put(it)

    snap = store.snapshot()
    assert len(snap) == len(items)
    assert all(a is b for a, b in zip(snap, items))  # order preserved, same object refs
    assert snap is not store._items  # copy, not alias
    assert store.qsize() == 3  # not consumed


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
