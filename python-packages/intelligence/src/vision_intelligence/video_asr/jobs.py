"""In-process asyncio job manager."""
from __future__ import annotations

import asyncio
from typing import Awaitable


class JobManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(self, job_id: str, coro: Awaitable) -> str:
        task = asyncio.create_task(coro, name=job_id)
        self._tasks[job_id] = task
        return job_id

    def is_running(self, job_id: str) -> bool:
        t = self._tasks.get(job_id)
        return bool(t and not t.done())

    async def wait(self, job_id: str) -> None:
        t = self._tasks.get(job_id)
        if t is not None:
            try:
                await t
            except Exception:
                pass

    def get_error(self, job_id: str) -> str | None:
        t = self._tasks.get(job_id)
        if t is None or not t.done():
            return None
        exc = t.exception()
        return repr(exc) if exc else None
