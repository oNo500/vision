# python-packages/live/src/vision_live/rag_library_store.py
"""Async CRUD for RagLibrary objects in SQLite."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RagLibraryStore:
    """Thin async CRUD wrapper around the rag_libraries table."""

    def __init__(self, conn: "aiosqlite.Connection") -> None:
        self._conn = conn

    async def create(self, lib_id: str, name: str) -> dict:
        existing = await self.get(lib_id)
        if existing is not None:
            raise ValueError(f"Library '{lib_id}' already exists")
        now = _now_iso()
        await self._conn.execute(
            "INSERT INTO rag_libraries (id, name, created_at) VALUES (?, ?, ?)",
            (lib_id, name, now),
        )
        await self._conn.commit()
        return {"id": lib_id, "name": name, "created_at": now}

    async def list_all(self) -> list[dict]:
        rows = []
        async with self._conn.execute(
            "SELECT id, name, created_at FROM rag_libraries ORDER BY created_at DESC"
        ) as cur:
            async for row in cur:
                rows.append({"id": row[0], "name": row[1], "created_at": row[2]})
        return rows

    async def get(self, lib_id: str) -> dict | None:
        async with self._conn.execute(
            "SELECT id, name, created_at FROM rag_libraries WHERE id = ?", (lib_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {"id": row[0], "name": row[1], "created_at": row[2]}

    async def delete(self, lib_id: str) -> None:
        await self._conn.execute("DELETE FROM rag_libraries WHERE id = ?", (lib_id,))
        await self._conn.commit()
