"""SQLite persistence via aiosqlite."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tts_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content       TEXT NOT NULL,
    speech_prompt TEXT,
    source        TEXT,
    ts            REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS event_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    type    TEXT NOT NULL,
    payload TEXT NOT NULL,
    ts      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS live_plans (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    data       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    """Async SQLite wrapper. Use `await db.init()` before any other call."""

    def __init__(self, path: str = "vision.db") -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        logger.info("Database ready at %s", self._path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def log_tts(
        self, content: str, speech_prompt: str | None, source: str, ts: float
    ) -> None:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call await db.init() first.")
        await self._conn.execute(
            "INSERT INTO tts_log (content, speech_prompt, source, ts) VALUES (?, ?, ?, ?)",
            (content, speech_prompt, source, ts),
        )
        await self._conn.commit()

    async def log_event(self, event_type: str, payload: dict, ts: float) -> None:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call await db.init() first.")
        await self._conn.execute(
            "INSERT INTO event_log (type, payload, ts) VALUES (?, ?, ?)",
            (event_type, json.dumps(payload, ensure_ascii=False), ts),
        )
        await self._conn.commit()

    async def get_history(
        self, limit: int = 100, type_filter: str | None = None
    ) -> list[dict]:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call await db.init() first.")
        limit = min(limit, 500)
        rows: list[dict] = []

        if type_filter != "events":
            async with self._conn.execute(
                "SELECT content, speech_prompt, source, ts FROM tts_log ORDER BY ts DESC",
            ) as cur:
                async for row in cur:
                    rows.append({
                        "type": "tts_output",
                        "ts": row[3],
                        "payload": {
                            "content": row[0],
                            "speech_prompt": row[1],
                            "source": row[2],
                        },
                    })

        if type_filter != "tts_output":
            async with self._conn.execute(
                "SELECT type, payload, ts FROM event_log ORDER BY ts DESC",
            ) as cur:
                async for row in cur:
                    payload = json.loads(row[1])
                    rows.append({"type": row[0], "ts": row[2], "payload": payload})

        rows.sort(key=lambda r: r["ts"], reverse=True)
        return rows[:limit]
