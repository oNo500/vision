"""Thread-safe ordered container — a Queue-compatible replacement that also
supports future mutation-by-id operations (remove / move / edit).

Producer/consumer API mirrors `queue.Queue` so existing consumer loops keep
working. Items must expose an `id: str` attribute; we rely on that for the
id-based mutations added later.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Protocol


class _HasId(Protocol):
    id: str


class OrderedItemStore[T: _HasId]:
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
                    deadline = time.monotonic() + timeout
                    while len(self._items) >= self._maxsize:
                        remaining = deadline - time.monotonic()
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
                deadline = time.monotonic() + timeout
                while not self._items:
                    remaining = deadline - time.monotonic()
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
