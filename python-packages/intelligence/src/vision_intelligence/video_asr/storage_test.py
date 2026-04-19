"""Tests for video_asr storage layer (schema + CRUD + FTS5)."""
from __future__ import annotations

import pytest
import aiosqlite

from vision_intelligence.video_asr.models import (
    RawTranscript, SegmentRecord, SourceMetadata, StageManifest, StyleProfile,
)
from vision_intelligence.video_asr.storage import VideoAsrStorage


@pytest.fixture
async def storage(tmp_path):
    db_path = tmp_path / "test.db"
    conn = await aiosqlite.connect(db_path)
    st = VideoAsrStorage(conn)
    await st.init_schema()
    yield st
    await conn.close()


async def test_init_schema_creates_all_tables(storage):
    conn = storage._conn
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','virtual') ORDER BY name"
    )
    names = {row[0] for row in await cur.fetchall()}
    for t in (
        "video_sources", "transcript_segments", "transcript_fts",
        "style_profiles", "pipeline_runs", "llm_usage",
        "asr_jobs", "asr_job_videos",
    ):
        assert t in names, f"missing {t} in {names}"


async def test_upsert_video_source(storage):
    meta = SourceMetadata(
        video_id="abc", source="youtube",
        url="https://www.youtube.com/watch?v=abc",
        title="t", uploader="u", duration_sec=1.0,
    )
    await storage.upsert_video_source(meta, asr_model="gemini-2.5-flash", bgm_removed=True)
    row = await storage.get_video_source("abc")
    assert row["video_id"] == "abc"
    assert row["reviewed"] == 0


async def test_write_segments_and_fts_search(storage):
    raw = RawTranscript(
        video_id="abc", source="youtube",
        url="https://www.youtube.com/watch?v=abc",
        title="t", uploader="u", duration_sec=10.0,
        asr_model="gemini-2.5-flash", asr_version="v1",
        processed_at="2026-04-18T00:00:00+08:00",
        bgm_removed=True,
        segments=[
            SegmentRecord(idx=0, start=0.0, end=2.0, speaker="host",
                          text="家人们晚上好", text_normalized="家人们 晚上 好",
                          confidence=0.95, chunk_id=0),
            SegmentRecord(idx=1, start=2.0, end=4.0, speaker="guest",
                          text="谢谢主播", text_normalized="谢谢 主播",
                          confidence=0.9, chunk_id=0),
        ],
    )
    await storage.upsert_video_source(
        SourceMetadata(video_id=raw.video_id, source=raw.source, url=raw.url,
                       title=raw.title, uploader=raw.uploader, duration_sec=raw.duration_sec),
        asr_model=raw.asr_model, bgm_removed=raw.bgm_removed,
    )
    await storage.write_segments(raw)

    hits = await storage.search_segments("晚上", limit=5)
    assert len(hits) == 1
    assert hits[0]["video_id"] == "abc"
    assert hits[0]["idx"] == 0


async def test_pipeline_run_upsert(storage):
    await storage.set_pipeline_run(
        video_id="abc", stage="ingest", status="running",
        started_at="2026-04-18T00:00:00+08:00",
    )
    await storage.set_pipeline_run(
        video_id="abc", stage="ingest", status="done",
        started_at="2026-04-18T00:00:00+08:00",
        finished_at="2026-04-18T00:01:00+08:00",
        duration_sec=60.0,
    )
    row = await storage.get_pipeline_run("abc", "ingest")
    assert row["status"] == "done"
    assert row["duration_sec"] == 60.0


async def test_style_profile_roundtrip(storage):
    await storage.upsert_video_source(
        SourceMetadata(video_id="abc", source="youtube",
                       url="u", title=None, uploader=None, duration_sec=None),
        asr_model="m", bgm_removed=True,
    )
    sp = StyleProfile(
        video_id="abc", host_speaking_ratio=0.8,
        speaker_count={"host": 1, "guest": 0, "other": 0, "unknown": 0},
        top_phrases=[], catchphrases=[], opening_hooks=[],
        cta_patterns=[], transition_patterns=[],
        sentence_length={"p50": 12.0, "p90": 28.0, "unit": "chars"},
        tone_tags=[], english_ratio=0.0,
    )
    await storage.upsert_style_profile(sp)
    got = await storage.get_style_profile("abc")
    assert got.video_id == "abc"


async def test_llm_usage_logging(storage):
    await storage.log_llm_usage(
        video_id="abc", stage="transcribe", model="gemini-2.5-flash",
        input_tokens=1000, output_tokens=200, estimated_cost_usd=0.01,
        called_at="2026-04-18T00:00:00+08:00",
    )
    total = await storage.sum_cost("abc")
    assert total == 0.01


async def test_asr_job_upsert_and_idempotent(storage):
    urls = ["https://a", "https://b"]
    job_id = await storage.create_or_get_job(urls, source="cli")
    again = await storage.create_or_get_job(urls, source="cli")
    assert job_id == again
