# python-packages/live/src/vision_live/rag_library_store_test.py
"""Tests for RagLibraryStore CRUD."""
from __future__ import annotations

import pytest
import aiosqlite


@pytest.fixture
async def conn(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as c:
        await c.executescript("""
            CREATE TABLE IF NOT EXISTS rag_libraries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        await c.commit()
        yield c


async def test_create_and_list(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    lib = await store.create("dong-yuhui", "董宇辉")
    assert lib["id"] == "dong-yuhui"
    assert lib["name"] == "董宇辉"
    libs = await store.list_all()
    assert len(libs) == 1
    assert libs[0]["id"] == "dong-yuhui"


async def test_get_existing(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    await store.create("lib-a", "Library A")
    result = await store.get("lib-a")
    assert result is not None
    assert result["name"] == "Library A"


async def test_get_missing_returns_none(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    result = await store.get("nonexistent")
    assert result is None


async def test_delete(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    await store.create("to-delete", "Delete Me")
    await store.delete("to-delete")
    assert await store.get("to-delete") is None


async def test_create_duplicate_raises(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    await store.create("dup", "First")
    with pytest.raises(ValueError, match="already exists"):
        await store.create("dup", "Second")
