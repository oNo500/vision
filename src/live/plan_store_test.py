"""Tests for PlanStore."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite
import pytest

from src.live.plan_store import PlanStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _make_plan(name: str = "Test Plan") -> dict:
    return {
        "name": name,
        "product": {"name": "P", "description": "D", "price": "99",
                    "highlights": ["h1"], "faq": [{"question": "Q", "answer": "A"}]},
        "persona": {"name": "主播", "style": "friendly",
                    "catchphrases": ["买它!"], "forbidden_words": ["违禁"]},
        "script": {"segments": [{"id": "s1", "text": "开场白", "duration": 60,
                                  "must_say": True, "keywords": ["产品"]}]},
    }


@pytest.fixture
async def store():
    async with aiosqlite.connect(":memory:") as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()
        yield PlanStore(conn)


@pytest.mark.asyncio
async def test_create_and_get(store: PlanStore):
    plan = await store.create(_make_plan())
    assert plan["id"]
    assert plan["name"] == "Test Plan"
    assert plan["created_at"]
    assert plan["updated_at"]

    fetched = await store.get(plan["id"])
    assert fetched is not None
    assert fetched["product"]["name"] == "P"
    assert fetched["persona"]["forbidden_words"] == ["违禁"]
    assert fetched["script"]["segments"][0]["must_say"] is True


@pytest.mark.asyncio
async def test_list(store: PlanStore):
    await store.create(_make_plan("Plan A"))
    await store.create(_make_plan("Plan B"))
    plans = await store.list_all()
    assert len(plans) == 2
    # list_all returns summary only (id, name, updated_at)
    assert "product" not in plans[0]
    names = {p["name"] for p in plans}
    assert names == {"Plan A", "Plan B"}


@pytest.mark.asyncio
async def test_update(store: PlanStore):
    plan = await store.create(_make_plan())
    update_data = {k: v for k, v in plan.items() if k not in ("id", "created_at", "updated_at")}
    update_data["name"] = "Renamed"
    updated = await store.update(plan["id"], update_data)
    assert updated["name"] == "Renamed"
    assert updated["updated_at"] >= plan["updated_at"]


@pytest.mark.asyncio
async def test_delete(store: PlanStore):
    plan = await store.create(_make_plan())
    await store.delete(plan["id"])
    assert await store.get(plan["id"]) is None


@pytest.mark.asyncio
async def test_get_nonexistent(store: PlanStore):
    result = await store.get("nonexistent-id")
    assert result is None
