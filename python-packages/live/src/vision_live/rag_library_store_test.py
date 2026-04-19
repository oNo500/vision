# python-packages/live/src/vision_live/rag_library_store_test.py
"""Tests for RagLibraryStore CRUD."""
from __future__ import annotations

import pytest
import aiosqlite

from vision_live.rag_library_store import RagLibraryStore
from vision_shared.db import _SCHEMA


@pytest.fixture
async def conn(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as c:
        await c.executescript(_SCHEMA)
        await c.commit()
        yield c


@pytest.fixture
async def store(conn):
    return RagLibraryStore(conn)


async def test_create_and_list(store):
    lib = await store.create("dong-yuhui", "董宇辉")
    assert lib["id"] == "dong-yuhui"
    assert lib["name"] == "董宇辉"
    libs = await store.list_all()
    assert len(libs) == 1
    assert libs[0]["id"] == "dong-yuhui"


async def test_get_existing(store):
    await store.create("lib-a", "Library A")
    result = await store.get("lib-a")
    assert result is not None
    assert result["name"] == "Library A"


async def test_get_missing_returns_none(store):
    result = await store.get("nonexistent")
    assert result is None


async def test_delete(store):
    await store.create("to-delete", "Delete Me")
    await store.delete("to-delete")
    assert await store.get("to-delete") is None


async def test_create_duplicate_raises(store):
    await store.create("dup", "First")
    with pytest.raises(ValueError, match="already exists"):
        await store.create("dup", "Second")


async def test_delete_nonexistent(store):
    await store.delete("does-not-exist")
    assert await store.get("does-not-exist") is None
