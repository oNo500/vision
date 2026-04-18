"""Tests for SQLite db layer using in-memory database."""
import asyncio
import pytest
import pytest_asyncio
from vision_shared.db import Database


@pytest_asyncio.fixture
async def db():
    d = Database(":memory:")
    await d.init()
    yield d
    await d.close()


@pytest.mark.asyncio
async def test_init_creates_tables(db):
    rows = await db._conn.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    names = {r[0] for r in rows}
    assert "tts_log" in names
    assert "event_log" in names


@pytest.mark.asyncio
async def test_log_tts(db):
    await db.log_tts(content="hello", speech_prompt="calm", source="script", ts=1000.0)
    rows = await db._conn.execute_fetchall("SELECT content, source FROM tts_log")
    assert rows[0] == ("hello", "script")


@pytest.mark.asyncio
async def test_log_event(db):
    await db.log_event(event_type="danmaku", payload={"user": "A", "text": "hi"}, ts=1001.0)
    rows = await db._conn.execute_fetchall("SELECT type FROM event_log")
    assert rows[0][0] == "danmaku"


@pytest.mark.asyncio
async def test_get_history_tts_only(db):
    await db.log_tts("hello", "calm", "script", 1000.0)
    await db.log_event("danmaku", {"user": "A"}, 1001.0)
    rows = await db.get_history(limit=10, type_filter="tts_output")
    assert len(rows) == 1
    assert rows[0]["type"] == "tts_output"


@pytest.mark.asyncio
async def test_get_history_events_only(db):
    await db.log_tts("hello", "calm", "script", 1000.0)
    await db.log_event("danmaku", {"user": "A"}, 1001.0)
    rows = await db.get_history(limit=10, type_filter="events")
    assert len(rows) == 1
    # type column is the event_log.type value, not overwritten by payload keys
    assert rows[0]["type"] == "danmaku"


@pytest.mark.asyncio
async def test_get_history_all_merged_sorted(db):
    await db.log_tts("hello", "calm", "script", 1000.0)
    await db.log_event("danmaku", {"user": "A"}, 999.0)
    rows = await db.get_history(limit=10, type_filter=None)
    assert len(rows) == 2
    # sorted by ts descending
    assert rows[0]["ts"] == 1000.0
    assert rows[1]["ts"] == 999.0


@pytest.mark.asyncio
async def test_get_history_respects_limit(db):
    for i in range(5):
        await db.log_tts(f"msg{i}", None, "script", float(i))
    rows = await db.get_history(limit=3, type_filter="tts_output")
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_get_history_limit_across_tables(db):
    for i in range(3):
        await db.log_tts(f"tts{i}", None, "script", float(i + 10))
    for i in range(3):
        await db.log_event("danmaku", {"user": f"u{i}"}, float(i))
    rows = await db.get_history(limit=4, type_filter=None)
    assert len(rows) == 4
    # first 4 by ts descending: tts2(12), tts1(11), tts0(10), danmaku2(2)
    assert rows[0]["ts"] == 12.0
    assert rows[3]["ts"] == 2.0
