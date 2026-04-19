# python-packages/api/src/vision_api/rag_library_routes_test.py
"""Integration tests for /api/intelligence/rag-libraries routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def app(tmp_path, monkeypatch):
    import aiosqlite
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    from vision_api.settings import get_settings
    get_settings.cache_clear()
    from vision_api.main import create_app
    from vision_live.rag_library_store import RagLibraryStore
    from vision_intelligence.video_asr.config import VideoAsrSettings

    application = create_app()
    db_path = tmp_path / "test.db"
    conn = await aiosqlite.connect(db_path)
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS rag_libraries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    await conn.commit()
    application.state.rag_library_store = RagLibraryStore(conn)
    settings = VideoAsrSettings()
    settings.output_root = str(tmp_path / "transcripts")
    application.state.video_asr_settings = settings
    application.state.rag_builds = {}
    yield application
    await conn.close()


@pytest.fixture
async def client(app):
    headers = {"X-API-Key": "test-key"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    ) as c:
        yield c


async def test_create_and_list_libraries(client):
    r = await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "dong-yuhui", "name": "董宇辉"},
    )
    assert r.status_code == 201
    assert r.json()["id"] == "dong-yuhui"

    r = await client.get("/api/intelligence/rag-libraries/")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_library(client, tmp_path):
    await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "to-del", "name": "Delete Me"},
    )
    r = await client.delete("/api/intelligence/rag-libraries/to-del")
    assert r.status_code == 204

    r = await client.get("/api/intelligence/rag-libraries/")
    assert r.json() == []


async def test_import_transcript_missing_video(client):
    # Create library first
    await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "my-lib", "name": "My Lib"},
    )
    r = await client.post(
        "/api/intelligence/rag-libraries/my-lib/import-transcript",
        json={"video_id": "nonexistent"},
    )
    assert r.status_code == 404


async def test_import_transcript_success(client, tmp_path):
    # Create library
    await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "my-lib", "name": "My Lib"},
    )

    # Seed transcript output
    video_dir = tmp_path / "transcripts" / "vid123"
    video_dir.mkdir(parents=True)
    (video_dir / "transcript.md").write_text("# Transcript\nhello world", encoding="utf-8")
    (video_dir / "summary.md").write_text("# Summary\ngreat video", encoding="utf-8")

    r = await client.post(
        "/api/intelligence/rag-libraries/my-lib/import-transcript",
        json={"video_id": "vid123"},
    )
    assert r.status_code == 200
    imported = r.json()["imported"]
    assert "competitor_clips/vid123.md" in imported
    assert "scripts/vid123_summary.md" in imported


async def test_create_duplicate_returns_409(client):
    await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "dup-lib", "name": "First"},
    )
    r = await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "dup-lib", "name": "Second"},
    )
    assert r.status_code == 409
