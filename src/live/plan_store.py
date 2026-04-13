"""PlanStore — async CRUD for LivePlan objects in SQLite."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlanStore:
    """Thin async CRUD wrapper around the live_plans table.

    Args:
        conn: An open aiosqlite.Connection (managed by Database).
    """

    def __init__(self, conn: "aiosqlite.Connection") -> None:
        self._conn = conn

    async def create(self, data: dict) -> dict:
        """Insert a new plan. Returns the full plan dict with id + timestamps."""
        plan_id = str(uuid.uuid4())
        now = _now_iso()
        plan = {
            "id": plan_id,
            "name": data["name"],
            "created_at": now,
            "updated_at": now,
            "product": data.get("product", {}),
            "persona": data.get("persona", {}),
            "script": data.get("script", {"segments": []}),
        }
        await self._conn.execute(
            "INSERT INTO live_plans (id, name, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (plan_id, plan["name"], json.dumps(plan, ensure_ascii=False), now, now),
        )
        await self._conn.commit()
        return plan

    async def list_all(self) -> list[dict]:
        """Return summary rows: id, name, updated_at (no nested data)."""
        rows = []
        async with self._conn.execute(
            "SELECT id, name, updated_at FROM live_plans ORDER BY updated_at DESC"
        ) as cur:
            async for row in cur:
                rows.append({"id": row[0], "name": row[1], "updated_at": row[2]})
        return rows

    async def get(self, plan_id: str) -> dict | None:
        """Return full plan dict or None if not found."""
        async with self._conn.execute(
            "SELECT data FROM live_plans WHERE id = ?", (plan_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    async def update(self, plan_id: str, data: dict) -> dict | None:
        """Replace plan data. Returns updated plan or None if not found."""
        existing = await self.get(plan_id)
        if existing is None:
            return None
        now = _now_iso()
        updated = {
            **existing,
            "name": data.get("name", existing["name"]),
            "updated_at": now,
            "product": data.get("product", existing["product"]),
            "persona": data.get("persona", existing["persona"]),
            "script": data.get("script", existing["script"]),
        }
        await self._conn.execute(
            "UPDATE live_plans SET name = ?, data = ?, updated_at = ? WHERE id = ?",
            (updated["name"], json.dumps(updated, ensure_ascii=False), now, plan_id),
        )
        await self._conn.commit()
        return updated

    async def delete(self, plan_id: str) -> None:
        """Delete plan by id (no-op if not found)."""
        await self._conn.execute("DELETE FROM live_plans WHERE id = ?", (plan_id,))
        await self._conn.commit()
