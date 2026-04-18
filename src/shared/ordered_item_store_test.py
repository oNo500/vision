"""Tests for OrderedItemStore — Queue-compatible core API."""
from __future__ import annotations

import dataclasses
import queue
import threading

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
