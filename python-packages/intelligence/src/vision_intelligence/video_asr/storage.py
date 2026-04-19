"""SQLite storage + FTS5 for video ASR pipeline."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import aiosqlite

from vision_intelligence.video_asr.models import (
    RawTranscript, SegmentRecord, SourceMetadata, StageManifest,
    StageName, StageStatus, StyleProfile,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_sources (
  video_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  uploader TEXT,
  duration_sec REAL,
  downloaded_at TEXT,
  processed_at TEXT,
  bgm_removed INTEGER,
  asr_model TEXT,
  reviewed INTEGER NOT NULL DEFAULT 0,
  reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS transcript_segments (
  video_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  start REAL NOT NULL,
  end REAL NOT NULL,
  speaker TEXT NOT NULL,
  text TEXT NOT NULL,
  text_normalized TEXT NOT NULL,
  chunk_id INTEGER,
  PRIMARY KEY (video_id, idx),
  FOREIGN KEY (video_id) REFERENCES video_sources(video_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
  video_id UNINDEXED,
  idx UNINDEXED,
  text_normalized,
  tokenize='unicode61 remove_diacritics 0'
);

CREATE TABLE IF NOT EXISTS style_profiles (
  video_id TEXT PRIMARY KEY,
  profile_json TEXT NOT NULL,
  FOREIGN KEY (video_id) REFERENCES video_sources(video_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  video_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  duration_sec REAL,
  error TEXT,
  PRIMARY KEY (video_id, stage)
);

CREATE TABLE IF NOT EXISTS llm_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT,
  stage TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  estimated_cost_usd REAL,
  called_at TEXT
);

CREATE TABLE IF NOT EXISTS asr_jobs (
  job_id TEXT PRIMARY KEY,
  created_at TEXT,
  source TEXT,
  status TEXT,
  video_count INTEGER,
  urls_hash TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS asr_job_videos (
  job_id TEXT,
  video_id TEXT,
  PRIMARY KEY (job_id, video_id),
  FOREIGN KEY (job_id) REFERENCES asr_jobs(job_id)
);
"""


def _urls_hash(urls: list[str]) -> str:
    canonical = "\n".join(sorted(urls))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


class VideoAsrStorage:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = aiosqlite.Row

    async def init_schema(self) -> None:
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def upsert_video_source(
        self, meta: SourceMetadata, *, asr_model: str, bgm_removed: bool,
    ) -> None:
        await self._conn.execute(
            """INSERT INTO video_sources
               (video_id, source, url, title, uploader, duration_sec,
                downloaded_at, bgm_removed, asr_model)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(video_id) DO UPDATE SET
                 source=excluded.source, url=excluded.url, title=excluded.title,
                 uploader=excluded.uploader, duration_sec=excluded.duration_sec,
                 bgm_removed=excluded.bgm_removed, asr_model=excluded.asr_model""",
            (meta.video_id, meta.source, meta.url, meta.title, meta.uploader,
             meta.duration_sec, _now_iso(), int(bgm_removed), asr_model),
        )
        await self._conn.commit()

    async def get_video_source(self, video_id: str) -> dict | None:
        cur = await self._conn.execute(
            "SELECT * FROM video_sources WHERE video_id = ?", (video_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def write_segments(self, raw: RawTranscript) -> None:
        await self._conn.execute(
            "DELETE FROM transcript_segments WHERE video_id = ?", (raw.video_id,))
        await self._conn.execute(
            "DELETE FROM transcript_fts WHERE video_id = ?", (raw.video_id,))
        rows = [
            (raw.video_id, s.idx, s.start, s.end, s.speaker,
             s.text, s.text_normalized, s.chunk_id)
            for s in raw.segments
        ]
        await self._conn.executemany(
            """INSERT INTO transcript_segments
               (video_id, idx, start, end, speaker, text, text_normalized, chunk_id)
               VALUES (?,?,?,?,?,?,?,?)""", rows)
        await self._conn.executemany(
            "INSERT INTO transcript_fts (video_id, idx, text_normalized) VALUES (?,?,?)",
            [(raw.video_id, s.idx, s.text_normalized) for s in raw.segments])
        await self._conn.execute(
            "UPDATE video_sources SET processed_at = ? WHERE video_id = ?",
            (_now_iso(), raw.video_id))
        await self._conn.commit()

    async def search_segments(self, q: str, limit: int = 50) -> list[dict]:
        cur = await self._conn.execute(
            """SELECT f.video_id, f.idx, s.text, s.start, s.end, s.speaker
               FROM transcript_fts f
               JOIN transcript_segments s
                 ON s.video_id = f.video_id AND s.idx = f.idx
               WHERE transcript_fts MATCH ?
               LIMIT ?""", (q, limit))
        return [dict(r) for r in await cur.fetchall()]

    async def set_pipeline_run(
        self, *, video_id: str, stage: str, status: str,
        started_at: str | None = None, finished_at: str | None = None,
        duration_sec: float | None = None, error: str | None = None,
    ) -> None:
        await self._conn.execute(
            """INSERT INTO pipeline_runs
               (video_id, stage, status, started_at, finished_at, duration_sec, error)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(video_id, stage) DO UPDATE SET
                 status=excluded.status,
                 started_at=COALESCE(excluded.started_at, pipeline_runs.started_at),
                 finished_at=excluded.finished_at,
                 duration_sec=excluded.duration_sec,
                 error=excluded.error""",
            (video_id, stage, status, started_at, finished_at, duration_sec, error))
        await self._conn.commit()

    async def get_pipeline_run(self, video_id: str, stage: str) -> dict | None:
        cur = await self._conn.execute(
            "SELECT * FROM pipeline_runs WHERE video_id = ? AND stage = ?",
            (video_id, stage))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def upsert_style_profile(self, sp: StyleProfile) -> None:
        await self._conn.execute(
            """INSERT INTO style_profiles (video_id, profile_json)
               VALUES (?, ?)
               ON CONFLICT(video_id) DO UPDATE SET profile_json = excluded.profile_json""",
            (sp.video_id, sp.model_dump_json()))
        await self._conn.commit()

    async def get_style_profile(self, video_id: str) -> StyleProfile | None:
        cur = await self._conn.execute(
            "SELECT profile_json FROM style_profiles WHERE video_id = ?", (video_id,))
        row = await cur.fetchone()
        return StyleProfile.model_validate_json(row[0]) if row else None

    async def log_llm_usage(
        self, *, video_id: str, stage: str, model: str,
        input_tokens: int, output_tokens: int, estimated_cost_usd: float,
        called_at: str,
    ) -> None:
        await self._conn.execute(
            """INSERT INTO llm_usage
               (video_id, stage, model, input_tokens, output_tokens,
                estimated_cost_usd, called_at)
               VALUES (?,?,?,?,?,?,?)""",
            (video_id, stage, model, input_tokens, output_tokens,
             estimated_cost_usd, called_at))
        await self._conn.commit()

    async def sum_cost(self, video_id: str | None = None) -> float:
        q = "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM llm_usage"
        args: tuple = ()
        if video_id is not None:
            q += " WHERE video_id = ?"
            args = (video_id,)
        cur = await self._conn.execute(q, args)
        row = await cur.fetchone()
        return float(row[0])

    async def create_or_get_job(
        self, urls: list[str], *, source: str = "cli",
    ) -> str:
        h = _urls_hash(urls)
        cur = await self._conn.execute(
            "SELECT job_id FROM asr_jobs WHERE urls_hash = ?",
            (h,))
        row = await cur.fetchone()
        if row:
            return row[0]
        job_id = str(uuid.uuid4())
        await self._conn.execute(
            """INSERT INTO asr_jobs
               (job_id, created_at, source, status, video_count, urls_hash)
               VALUES (?, ?, ?, 'running', ?, ?)""",
            (job_id, _now_iso(), source, len(urls), h))
        await self._conn.commit()
        return job_id

    async def set_job_status(self, job_id: str, status: str) -> None:
        await self._conn.execute(
            "UPDATE asr_jobs SET status = ? WHERE job_id = ?", (status, job_id))
        await self._conn.commit()

    async def link_job_video(self, job_id: str, video_id: str) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO asr_job_videos (job_id, video_id) VALUES (?, ?)",
            (job_id, video_id))
        await self._conn.commit()
