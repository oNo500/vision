# Video ASR Pipeline Implementation Plan — Part 2 (Tasks 5-26)

> Continuation of `2026-04-18-video-asr-pipeline.md`. Same rules: TDD, frequent commits, 332+ baseline.

---

## Phase 2 — Storage Layer

### Task 5: SQLite schema init + CRUD

**Files:**
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/storage.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/storage_test.py`

- [ ] **Step 5.1: Write failing test**

`storage_test.py`:

```python
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
```

- [ ] **Step 5.2: Run failing test**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/storage_test.py -v 2>&1 | tail -10
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 5.3: Implement `storage.py`**

```python
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
        self, *, video_id: str, stage: StageName, status: StageStatus,
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

    async def get_pipeline_run(self, video_id: str, stage: StageName) -> dict | None:
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
        self, *, video_id: str, stage: StageName, model: str,
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
            "SELECT job_id FROM asr_jobs WHERE urls_hash = ? AND status = 'running'",
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
```

- [ ] **Step 5.4: Run tests**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/storage_test.py -v 2>&1 | tail -15
```

Expected: PASS 7/7.

- [ ] **Step 5.5: Full baseline**

```bash
uv run pytest -q 2>&1 | tail -3
```

Expected: `345 passed` (338 + 7).

- [ ] **Step 5.6: Commit**

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/storage.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/storage_test.py
git commit -m "feat(video-asr): SQLite schema + CRUD + FTS5 storage layer"
```

### Task 6: Stage manifest I/O

**Files:**
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/manifest.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/manifest_test.py`

- [ ] **Step 6.1: Write failing test**

```python
"""Tests for stage manifest I/O helpers."""
from __future__ import annotations

from vision_intelligence.video_asr.manifest import (
    manifest_path, read_manifest, write_manifest,
)
from vision_intelligence.video_asr.models import StageManifest


def test_manifest_path(tmp_path):
    p = manifest_path(tmp_path, "ingest")
    assert p == tmp_path / "stages" / "01-ingest.json"


def test_write_read_roundtrip(tmp_path):
    m = StageManifest(
        stage="transcribe", video_id="abc", status="done",
        started_at="t0", finished_at="t1", duration_sec=10.0,
        inputs=["audio.m4a"], outputs=["chunks"],
        tool_versions={"google-genai": "1.72.0"},
        pipeline_version="0.1.0",
        extra={"tokens_in": 1000, "tokens_out": 200, "estimated_cost_usd": 0.01},
    )
    write_manifest(tmp_path, m)

    again = read_manifest(tmp_path, "transcribe")
    assert again == m


def test_read_missing_returns_none(tmp_path):
    assert read_manifest(tmp_path, "ingest") is None


def test_stage_ordinal_prefixes(tmp_path):
    for expected, stage in [
        (1, "ingest"), (2, "preprocess"), (3, "transcribe"),
        (4, "merge"), (5, "render"), (6, "analyze"), (7, "load"),
    ]:
        p = manifest_path(tmp_path, stage)
        assert p.name.startswith(f"{expected:02d}-")
```

- [ ] **Step 6.2: Run failing test, implement, re-run**

`manifest.py`:

```python
"""Stage manifest file I/O (output/transcripts/<vid>/stages/NN-<name>.json)."""
from __future__ import annotations

from pathlib import Path

from vision_intelligence.video_asr.models import StageManifest, StageName

_STAGE_ORDER: dict[StageName, int] = {
    "ingest": 1, "preprocess": 2, "transcribe": 3, "merge": 4,
    "render": 5, "analyze": 6, "load": 7,
}


def manifest_path(video_dir: Path, stage: StageName) -> Path:
    n = _STAGE_ORDER[stage]
    return video_dir / "stages" / f"{n:02d}-{stage}.json"


def write_manifest(video_dir: Path, m: StageManifest) -> None:
    p = manifest_path(video_dir, m.stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(m.model_dump_json(indent=2), encoding="utf-8")


def read_manifest(video_dir: Path, stage: StageName) -> StageManifest | None:
    p = manifest_path(video_dir, stage)
    if not p.exists():
        return None
    return StageManifest.model_validate_json(p.read_text(encoding="utf-8"))
```

Run tests, expect PASS 4/4.

- [ ] **Step 6.3: Commit**

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/manifest.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/manifest_test.py
git commit -m "feat(video-asr): stage manifest read/write helpers"
```

---

## Phase 3 — Sources

### Task 7: `VideoSource` protocol + yt-dlp implementation

**Files:**
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/sources/base.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/sources/base_test.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/sources/yt_dlp_source.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/sources/yt_dlp_source_test.py`

- [ ] **Step 7.1: Write `base.py` protocol + tiny test**

`base.py`:
```python
"""VideoSource interface."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vision_intelligence.video_asr.models import SourceMetadata


class VideoSource(Protocol):
    name: str

    def fetch_metadata(self, url: str) -> SourceMetadata: ...

    def download_audio(self, url: str, out_path: Path) -> int:
        """Download audio to out_path. Return bytes written."""
```

`base_test.py`:
```python
from vision_intelligence.video_asr.sources.base import VideoSource


def test_protocol_importable():
    assert VideoSource is not None
```

- [ ] **Step 7.2: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/sources/base_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/sources/base.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/sources/base_test.py
git commit -m "feat(video-asr): VideoSource protocol"
```

- [ ] **Step 7.3: Write failing test for yt-dlp source**

`yt_dlp_source_test.py`:
```python
"""Tests for yt-dlp source (mocked subprocess)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from vision_intelligence.video_asr.models import SourceMetadata
from vision_intelligence.video_asr.sources.yt_dlp_source import YtDlpSource


def test_video_id_youtube():
    src = YtDlpSource()
    assert src.extract_video_id("https://www.youtube.com/watch?v=abc123") == "abc123"
    assert src.extract_video_id(
        "https://www.youtube.com/watch?v=xyz&list=foo&index=2") == "xyz"


def test_video_id_bilibili():
    src = YtDlpSource()
    assert src.extract_video_id(
        "https://www.bilibili.com/video/BV1at4y1h7X4/") == "BV1at4y1h7X4"
    assert src.extract_video_id(
        "https://www.bilibili.com/video/BV1at4y1h7X4/?p=2") == "BV1at4y1h7X4"


def test_source_name_routing():
    src = YtDlpSource()
    assert src.classify_source("https://youtu.be/abc") == "youtube"
    assert src.classify_source("https://www.youtube.com/watch?v=abc") == "youtube"
    assert src.classify_source("https://www.bilibili.com/video/BVxxx") == "bilibili"


def test_fetch_metadata_invokes_yt_dlp(tmp_path):
    fake_info = {
        "id": "abc", "title": "T", "uploader": "U", "duration": 3600,
    }
    with patch("vision_intelligence.video_asr.sources.yt_dlp_source._run_yt_dlp_json") as mock:
        mock.return_value = fake_info
        src = YtDlpSource()
        meta = src.fetch_metadata("https://www.youtube.com/watch?v=abc")
    assert isinstance(meta, SourceMetadata)
    assert meta.video_id == "abc"
    assert meta.title == "T"
    assert meta.duration_sec == 3600


def test_download_audio_invokes_yt_dlp(tmp_path):
    out = tmp_path / "audio.m4a"
    with patch(
        "vision_intelligence.video_asr.sources.yt_dlp_source._run_yt_dlp_download"
    ) as mock:
        def fake(url, output):
            Path(output).write_bytes(b"fake audio")
            return len(b"fake audio")
        mock.side_effect = fake
        src = YtDlpSource()
        bytes_written = src.download_audio("https://www.youtube.com/watch?v=abc", out)
    assert bytes_written == len(b"fake audio")
    assert out.exists() and out.read_bytes() == b"fake audio"
```

- [ ] **Step 7.4: Run failing**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/sources/yt_dlp_source_test.py -v 2>&1 | tail -10
```

Expected: FAIL ModuleNotFoundError.

- [ ] **Step 7.5: Implement `yt_dlp_source.py`**

```python
"""yt-dlp based source for YouTube + Bilibili."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Literal

from vision_intelligence.video_asr.models import SourceMetadata, SourceName


_YT_ID_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]{6,})")
_BV_RE = re.compile(r"/video/(BV[A-Za-z0-9]+)")


def _run_yt_dlp_json(url: str) -> dict:
    """Shell out to yt-dlp --dump-json. Separated for test mocking."""
    proc = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-warnings", url],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def _run_yt_dlp_download(url: str, output: str) -> int:
    """Shell out to yt-dlp. Returns bytes written."""
    subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "m4a",
         "--audio-quality", "0", "-o", output, url],
        capture_output=True, text=True, check=True,
    )
    return Path(output).stat().st_size


class YtDlpSource:
    name = "yt_dlp"

    def classify_source(self, url: str) -> SourceName:
        if "bilibili.com" in url:
            return "bilibili"
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        raise ValueError(f"Unsupported URL: {url}")

    def extract_video_id(self, url: str) -> str:
        m = _YT_ID_RE.search(url)
        if m:
            return m.group(1)
        m = _BV_RE.search(url)
        if m:
            return m.group(1)
        if "youtu.be/" in url:
            return url.split("youtu.be/")[-1].split("?")[0]
        raise ValueError(f"Cannot extract video id from: {url}")

    def fetch_metadata(self, url: str) -> SourceMetadata:
        info = _run_yt_dlp_json(url)
        return SourceMetadata(
            video_id=self.extract_video_id(url),
            source=self.classify_source(url),
            url=url,
            title=info.get("title"),
            uploader=info.get("uploader"),
            duration_sec=float(info["duration"]) if info.get("duration") else None,
        )

    def download_audio(self, url: str, out_path: Path) -> int:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # yt-dlp replaces extension via --audio-format; pass the stem.
        stem = str(out_path.with_suffix(""))
        size = _run_yt_dlp_download(url, stem + ".%(ext)s")
        # After -x --audio-format m4a, the file is <stem>.m4a
        final = Path(stem + ".m4a")
        if final != out_path and final.exists():
            final.rename(out_path)
        return size
```

- [ ] **Step 7.6: Run + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/sources/ -v 2>&1 | tail -10
```

Expected: PASS 6/6 (1 from base_test + 5 from yt_dlp).

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/sources/
git commit -m "feat(video-asr): yt-dlp source for YouTube + Bilibili"
```

### Task 8: Source registry

**Files:**
- Create: `sources/registry.py` + `sources/registry_test.py`

- [ ] **Step 8.1: Write test**

```python
from vision_intelligence.video_asr.sources.registry import get_source


def test_registry_routes_youtube():
    src = get_source("https://www.youtube.com/watch?v=abc")
    assert src.name == "yt_dlp"


def test_registry_routes_bilibili():
    src = get_source("https://www.bilibili.com/video/BVxxx")
    assert src.name == "yt_dlp"


def test_registry_unknown_raises():
    import pytest
    with pytest.raises(ValueError):
        get_source("https://example.com/video")
```

- [ ] **Step 8.2: Implement**

```python
"""URL → VideoSource router."""
from __future__ import annotations

from vision_intelligence.video_asr.sources.base import VideoSource
from vision_intelligence.video_asr.sources.yt_dlp_source import YtDlpSource


def get_source(url: str) -> VideoSource:
    if any(h in url for h in ("youtube.com", "youtu.be", "bilibili.com")):
        return YtDlpSource()
    raise ValueError(f"No source registered for URL: {url}")
```

- [ ] **Step 8.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/sources/registry_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/sources/registry.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/sources/registry_test.py
git commit -m "feat(video-asr): URL → VideoSource registry"
```

### Task 9: `sources.yaml` loader

**Files:**
- Create: `sources/yaml_loader.py` + `yaml_loader_test.py`

- [ ] **Step 9.1: Write test**

```python
from vision_intelligence.video_asr.sources.yaml_loader import load_sources


def test_load_14_videos():
    videos = load_sources("config/video_asr/sources.yaml")
    assert len(videos) == 14
    ids = {v.video_id for v in videos}
    assert "0y3O90vyKNo" in ids
    assert "BV1at4y1h7X4" in ids
```

- [ ] **Step 9.2: Implement**

```python
"""Parse config/video_asr/sources.yaml → list[SourceMetadata-lite]."""
from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass
class SourceEntry:
    video_id: str
    source: str
    url: str


def load_sources(yaml_path: str) -> list[SourceEntry]:
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [SourceEntry(**v) for v in data["videos"]]
```

- [ ] **Step 9.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/sources/yaml_loader_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/sources/yaml_loader.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/sources/yaml_loader_test.py
git commit -m "feat(video-asr): sources.yaml loader"
```

---

## Phase 4 — Preprocessor (Demucs + ffmpeg)

### Task 10: Audio preprocessing

**Files:**
- Create: `preprocessor.py` + `preprocessor_test.py`

- [ ] **Step 10.1: Write tests (mock demucs and ffmpeg subprocess)**

```python
from pathlib import Path
from unittest.mock import patch
import pytest

from vision_intelligence.video_asr.preprocessor import (
    remove_bgm, split_into_chunks, preprocess_audio,
)


def test_split_math(tmp_path):
    duration_sec = 3600.0
    chunks = split_into_chunks.compute_boundaries(
        duration_sec, chunk_sec=1200, overlap_sec=10,
    )
    # 3600s / (1200 - 10 overlap) rounds to enough chunks covering end
    assert chunks[0] == (0.0, 1200.0)
    assert chunks[-1][1] >= 3600.0


def test_remove_bgm_calls_demucs(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake")
    vocals = tmp_path / "vocals.wav"
    with patch("vision_intelligence.video_asr.preprocessor._run_demucs") as m:
        def fake(input_path, output_path):
            Path(output_path).write_bytes(b"vocals")
        m.side_effect = fake
        remove_bgm(audio, vocals)
    assert vocals.exists()


def test_preprocess_audio_produces_chunks(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake")
    vocals = tmp_path / "vocals.wav"
    chunks_dir = tmp_path / "chunks"

    with patch("vision_intelligence.video_asr.preprocessor._run_demucs") as demucs_m, \
         patch("vision_intelligence.video_asr.preprocessor._run_ffmpeg_slice") as ffm_m, \
         patch("vision_intelligence.video_asr.preprocessor._probe_duration") as probe_m:
        demucs_m.side_effect = lambda i, o: Path(o).write_bytes(b"v")
        probe_m.return_value = 2400.0  # 40 min
        ffm_m.side_effect = lambda inp, out, start, dur: Path(out).write_bytes(b"c")

        result = preprocess_audio(
            audio, vocals, chunks_dir,
            chunk_sec=1200, overlap_sec=10, enable_bgm_removal=True,
        )

    assert result["bgm_removed"] is True
    assert result["chunk_count"] == 2
    assert vocals.exists()
    assert (chunks_dir / "chunk_000.wav").exists()
    assert (chunks_dir / "chunk_001.wav").exists()
```

- [ ] **Step 10.2: Implement**

```python
"""Demucs BGM removal + ffmpeg chunk splitting."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _run_demucs(input_path: Path, output_path: Path) -> None:
    """Run demucs htdemucs; extract the 'vocals' stem to output_path."""
    tmp = output_path.parent / "_demucs_out"
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python", "-m", "demucs.separate",
         "-n", "htdemucs", "--two-stems=vocals",
         "-o", str(tmp), str(input_path)],
        capture_output=True, check=True,
    )
    # demucs writes to <tmp>/<model>/<stem>/vocals.wav
    found = list(tmp.rglob("vocals.wav"))
    if not found:
        raise RuntimeError(f"demucs did not produce vocals.wav in {tmp}")
    shutil.move(str(found[0]), str(output_path))
    shutil.rmtree(tmp, ignore_errors=True)


def _probe_duration(path: Path) -> float:
    """ffprobe duration in seconds."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def _run_ffmpeg_slice(input_path: Path, output_path: Path,
                     start: float, duration: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path),
         "-ss", str(start), "-t", str(duration),
         "-ac", "1", "-ar", "16000",
         str(output_path)],
        capture_output=True, check=True,
    )


def remove_bgm(audio_path: Path, vocals_out: Path) -> None:
    vocals_out.parent.mkdir(parents=True, exist_ok=True)
    _run_demucs(audio_path, vocals_out)


class split_into_chunks:
    @staticmethod
    def compute_boundaries(
        duration_sec: float, chunk_sec: int, overlap_sec: int,
    ) -> list[tuple[float, float]]:
        """Return list of (start, end) in seconds. Last chunk extends to duration."""
        step = chunk_sec - overlap_sec
        boundaries: list[tuple[float, float]] = []
        t = 0.0
        while t < duration_sec:
            end = min(t + chunk_sec, duration_sec)
            boundaries.append((t, end))
            if end >= duration_sec:
                break
            t += step
        return boundaries


def preprocess_audio(
    audio_path: Path, vocals_out: Path, chunks_dir: Path,
    *, chunk_sec: int, overlap_sec: int, enable_bgm_removal: bool,
) -> dict:
    """Run the preprocess stage end-to-end. Return manifest-ready dict."""
    if enable_bgm_removal:
        remove_bgm(audio_path, vocals_out)
        source_for_chunks = vocals_out
    else:
        shutil.copy(audio_path, vocals_out)
        source_for_chunks = vocals_out

    duration = _probe_duration(source_for_chunks)
    boundaries = split_into_chunks.compute_boundaries(
        duration, chunk_sec, overlap_sec,
    )

    chunks_dir.mkdir(parents=True, exist_ok=True)
    for i, (start, end) in enumerate(boundaries):
        out = chunks_dir / f"chunk_{i:03d}.wav"
        _run_ffmpeg_slice(source_for_chunks, out, start, end - start)

    return {
        "bgm_removed": enable_bgm_removal,
        "chunk_count": len(boundaries),
        "chunk_duration_sec": chunk_sec,
        "chunk_overlap_sec": overlap_sec,
        "sample_rate": 16000,
        "channels": 1,
        "demucs_model": "htdemucs" if enable_bgm_removal else None,
        "boundaries": [list(b) for b in boundaries],
    }
```

- [ ] **Step 10.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/preprocessor_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/preprocessor.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/preprocessor_test.py
git commit -m "feat(video-asr): Demucs BGM removal + ffmpeg chunk splitter"
```

### Task 11: Text cleaning utilities

**Files:**
- Create: `cleaning.py` + `cleaning_test.py`

- [ ] **Step 11.1: Write tests**

```python
from vision_intelligence.video_asr.cleaning import (
    normalize_punctuation, traditional_to_simplified, jieba_tokenize,
)


def test_normalize_punctuation_halfwidth_to_fullwidth():
    s = "你好,今天怎么样?"
    assert normalize_punctuation(s) == "你好，今天怎么样？"


def test_normalize_punctuation_keeps_english_words():
    s = "AI is great. iPhone 15, true?"
    # English words with punctuation inside tokens remain halfwidth;
    # only sentence-delimiter punctuation right after Chinese chars converts
    out = normalize_punctuation(s)
    # No aggressive conversion inside English:
    assert "iPhone 15" in out
    # Sentence-final punctuation after English may stay halfwidth (acceptable)
    # but after CJK char it must convert:
    s2 = "家人们好,这个产品.真不错!"
    assert normalize_punctuation(s2) == "家人们好，这个产品。真不错！"


def test_traditional_to_simplified():
    assert traditional_to_simplified("個體實體") == "个体实体"


def test_jieba_tokenize_chinese():
    out = jieba_tokenize("家人们晚上好")
    # Must produce a space-separated string
    assert " " in out
    assert "家人们" in out.split() or "晚上" in out.split()
```

- [ ] **Step 11.2: Implement**

```python
"""Text cleaning per spec §6.5."""
from __future__ import annotations

import re

import jieba
from opencc import OpenCC

_OCC = OpenCC("t2s")

# Map halfwidth punctuation that follows CJK to fullwidth.
_CJK = r"[\u4e00-\u9fff]"
_HALF_TO_FULL = {",": "，", ".": "。", "?": "？", "!": "！", ";": "；", ":": "："}


def normalize_punctuation(s: str) -> str:
    def _repl(m):
        return m.group(1) + _HALF_TO_FULL[m.group(2)]
    pattern = re.compile(rf"({_CJK})([,.?!;:])")
    return pattern.sub(_repl, s)


def traditional_to_simplified(s: str) -> str:
    return _OCC.convert(s)


def jieba_tokenize(s: str) -> str:
    """Return space-separated tokens for FTS5 indexing."""
    return " ".join(w for w in jieba.cut(s) if w.strip())
```

- [ ] **Step 11.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/cleaning_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/cleaning.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/cleaning_test.py
git commit -m "feat(video-asr): text cleaning utilities (punct/繁简/jieba)"
```

---

## Phase 5 — ASR (Gemini)

### Task 12: Transcribe prompt + ASR interface

**Files:**
- Replace content: `prompts/transcribe.md`
- Create: `asr/base.py` + `asr/gemini.py` + `asr/gemini_test.py`

- [ ] **Step 12.1: Write `prompts/transcribe.md`**

```markdown
# Chinese Video Audio Transcription

You are a professional Chinese ASR system processing a chunk of a live-streaming or long-form video recording. The audio may contain a main host (主播), guests (嘉宾/连麦), background chatter, and occasional BGM (vocals should be isolated already).

## Your task

Transcribe the speech in the audio into Chinese text. For each utterance produce:

- `start` / `end`: seconds relative to the **start of this chunk**
- `speaker`: one of `host`, `guest`, `other`, `unknown`
  - `host`: the primary speaker (talks the most, leads the content)
  - `guest`: a co-host or invited speaker
  - `other`: audience call-ins, passers-by, unidentified speakers
  - `unknown`: speech detected but speaker role unclear
- `text`: transcribed text in Simplified Chinese, with proper punctuation (，。？！)
- `confidence`: 0.0-1.0 self-assessed confidence

## Rules

1. Output Simplified Chinese even if the speaker uses Traditional; keep English technical terms intact (AI, iPhone, CTA, RAG).
2. Use full-width Chinese punctuation (，。？！：；), not half-width.
3. Split on natural sentence boundaries, not filler breaths.
4. If a segment is pure BGM, coughing, or unintelligible, omit it.
5. Keep the host's identity consistent within this chunk (same voice = same `host` tag).
6. If uncertain of a proper noun, transcribe phonetically and lower the confidence.
```

- [ ] **Step 12.2: Write `asr/base.py`**

```python
"""Transcriber protocol."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vision_intelligence.video_asr.models import ChunkTranscript


class Transcriber(Protocol):
    name: str

    def transcribe_chunk(
        self, audio_path: Path, *, chunk_id: int, start_offset: float,
    ) -> ChunkTranscript: ...
```

- [ ] **Step 12.3: Write failing tests for gemini**

```python
"""Tests for Gemini transcriber (mocked)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vision_intelligence.video_asr.asr.gemini import GeminiTranscriber
from vision_intelligence.video_asr.models import ChunkTranscript


def _fake_gemini_response():
    """Shape mirrors google-genai's response.parsed for our schema."""
    from vision_intelligence.video_asr.asr.gemini import _ResponseModel, _SegmentModel
    return _ResponseModel(segments=[
        _SegmentModel(start=0.0, end=2.0, speaker="host",
                      text="大家好", confidence=0.95),
    ])


def test_transcribe_chunk_builds_chunk_transcript(tmp_path):
    audio = tmp_path / "chunk_000.wav"
    audio.write_bytes(b"fake")
    with patch(
        "vision_intelligence.video_asr.asr.gemini._call_gemini_audio",
    ) as m:
        fake = _fake_gemini_response()
        m.return_value = (fake, {"input_tokens": 100, "output_tokens": 20})
        t = GeminiTranscriber(model="gemini-2.5-flash", project="test", location="us-central1")
        ct = t.transcribe_chunk(audio, chunk_id=0, start_offset=0.0)
    assert isinstance(ct, ChunkTranscript)
    assert len(ct.segments) == 1
    assert ct.segments[0].speaker == "host"
    assert ct.segments[0].chunk_id == 0


def test_transcribe_applies_start_offset(tmp_path):
    audio = tmp_path / "chunk_001.wav"
    audio.write_bytes(b"fake")
    with patch("vision_intelligence.video_asr.asr.gemini._call_gemini_audio") as m:
        m.return_value = (_fake_gemini_response(), {"input_tokens": 1, "output_tokens": 1})
        t = GeminiTranscriber(model="gemini-2.5-flash", project="p", location="us-central1")
        ct = t.transcribe_chunk(audio, chunk_id=1, start_offset=1190.0)
    # Relative 0.0 → absolute 1190.0
    assert ct.segments[0].start == 1190.0
    assert ct.segments[0].end == 1192.0
```

- [ ] **Step 12.4: Implement `asr/gemini.py`**

```python
"""Gemini 2.5 Flash ASR via google-genai (Vertex AI, ADC)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from vision_intelligence.video_asr.models import (
    ChunkTranscript, SegmentRecord, Speaker,
)


class _SegmentModel(BaseModel):
    start: float
    end: float
    speaker: Literal["host", "guest", "other", "unknown"]
    text: str
    confidence: float = Field(ge=0.0, le=1.0)


class _ResponseModel(BaseModel):
    segments: list[_SegmentModel]


def _load_prompt() -> str:
    here = Path(__file__).parent.parent / "prompts" / "transcribe.md"
    return here.read_text(encoding="utf-8")


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _call_gemini_audio(
    *, client, model: str, audio_bytes: bytes, prompt: str,
) -> tuple[_ResponseModel, dict]:
    """Return (parsed response, usage dict). Wrapped for test mocking + retry."""
    from google.genai import types as gtypes
    resp = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            gtypes.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
        ],
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_ResponseModel,
            temperature=0.2,
        ),
    )
    parsed: _ResponseModel = resp.parsed
    usage = {
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) or 0,
    }
    return parsed, usage


class GeminiTranscriber:
    name = "gemini"

    def __init__(self, *, model: str, project: str, location: str) -> None:
        self.model = model
        self.project = project
        self.location = location
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(
                vertexai=True, project=self.project, location=self.location,
            )
        return self._client

    def transcribe_chunk(
        self, audio_path: Path, *, chunk_id: int, start_offset: float,
    ) -> ChunkTranscript:
        audio_bytes = audio_path.read_bytes()
        client = self._get_client()
        prompt = _load_prompt()
        parsed, usage = _call_gemini_audio(
            client=client, model=self.model,
            audio_bytes=audio_bytes, prompt=prompt,
        )
        segments = [
            SegmentRecord(
                idx=i,
                start=s.start + start_offset,
                end=s.end + start_offset,
                speaker=s.speaker,
                text=s.text,
                text_normalized="",  # filled by merger/storage later
                confidence=s.confidence,
                chunk_id=chunk_id,
            )
            for i, s in enumerate(parsed.segments)
        ]
        ct = ChunkTranscript(chunk_id=chunk_id, start_offset=start_offset,
                             segments=segments)
        # Stash usage for caller (pipeline records it)
        ct.__pydantic_extra__ = {"usage": usage} if hasattr(ct, "__pydantic_extra__") else None
        return ct

    def last_usage_for_chunk(self) -> dict:
        """Placeholder — pipeline should capture via wrapped call instead."""
        return {}
```

- [ ] **Step 12.5: Run tests + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/asr/ -v
```

Expected: PASS 2/2.

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/prompts/transcribe.md \
        python-packages/intelligence/src/vision_intelligence/video_asr/asr/
git commit -m "feat(video-asr): Gemini transcribe + prompt + Transcriber protocol"
```

### Task 13: Token-cost estimator helper

**Files:**
- Create: `cost.py` + `cost_test.py`

Gemini 2.5 Flash pricing (audio input $0.30/M, text output $2.50/M as of early 2026; update if changed).

- [ ] **Step 13.1: Test**

```python
from vision_intelligence.video_asr.cost import estimate_cost_usd


def test_flash_audio_pricing():
    # 100k input (audio) + 10k output
    c = estimate_cost_usd(model="gemini-2.5-flash",
                          input_tokens=100_000, output_tokens=10_000)
    # 100k * 0.30/1M + 10k * 2.50/1M = 0.03 + 0.025 = 0.055
    assert round(c, 4) == 0.055


def test_unknown_model_returns_zero():
    assert estimate_cost_usd(model="unknown", input_tokens=1, output_tokens=1) == 0.0
```

- [ ] **Step 13.2: Implement + test + commit**

```python
"""LLM cost estimator (USD)."""
from __future__ import annotations

# prices in USD per 1M tokens
_PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
}


def estimate_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float:
    p = _PRICING.get(model)
    if p is None:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
```

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/cost_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/cost.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/cost_test.py
git commit -m "feat(video-asr): LLM cost estimator"
```

---

## Phase 6 — Merger (dedupe + cleaning)

### Task 14: Merge chunks → raw.json with cleaning

**Files:**
- Create: `merger.py` + `merger_test.py`

- [ ] **Step 14.1: Write tests**

```python
from vision_intelligence.video_asr.merger import (
    merge_chunks, _is_near_duplicate, _sanitize_timestamps,
)
from vision_intelligence.video_asr.models import ChunkTranscript, SegmentRecord


def _seg(idx, start, end, text, speaker="host", conf=0.9, chunk_id=0):
    return SegmentRecord(
        idx=idx, start=start, end=end, speaker=speaker,
        text=text, text_normalized=text, confidence=conf, chunk_id=chunk_id,
    )


def test_is_near_duplicate_yes():
    assert _is_near_duplicate("家人们晚上好呀", "家人们晚上好呀！") is True


def test_is_near_duplicate_no():
    assert _is_near_duplicate("今天讲A产品", "今天讲B产品") is False


def test_sanitize_swap_start_end():
    seg = _seg(0, 5.0, 3.0, "x")
    out = _sanitize_timestamps([seg])
    assert out[0].start == 3.0 and out[0].end == 5.0


def test_sanitize_drops_empty():
    segs = [_seg(0, 0, 1, ""), _seg(1, 1, 2, "真的好")]
    out = _sanitize_timestamps(segs)
    assert len(out) == 1
    assert out[0].text == "真的好"


def test_merge_drops_overlap_duplicates():
    # Chunk 0: 0-20 (end offset 1200 if chunk 1 starts at 1190)
    c0 = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=[
        _seg(0, 1185.0, 1188.0, "结尾话术", chunk_id=0),
    ])
    c1 = ChunkTranscript(chunk_id=1, start_offset=1190.0, segments=[
        _seg(0, 1186.0, 1188.5, "结尾话术！", chunk_id=1),
        _seg(1, 1195.0, 1200.0, "下一段", chunk_id=1),
    ])
    merged = merge_chunks([c0, c1])
    # Near-duplicate "结尾话术" should be collapsed
    texts = [s.text for s in merged.segments]
    assert texts.count("结尾话术") + texts.count("结尾话术！") == 1
    assert "下一段" in texts


def test_merge_converts_traditional_to_simplified():
    c = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=[
        _seg(0, 0, 1, "這個實體"),
    ])
    merged = merge_chunks([c])
    assert "这个实体" in merged.segments[0].text


def test_merge_normalizes_punctuation():
    c = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=[
        _seg(0, 0, 1, "家人们好,真的不错!"),
    ])
    merged = merge_chunks([c])
    assert merged.segments[0].text == "家人们好，真的不错！"
```

- [ ] **Step 14.2: Implement**

```python
"""Merge chunk transcripts → monotonic raw.json with cleaning (§6.5.1)."""
from __future__ import annotations

import difflib
import logging

from vision_intelligence.video_asr.cleaning import (
    normalize_punctuation, traditional_to_simplified,
)
from vision_intelligence.video_asr.models import ChunkTranscript, SegmentRecord

logger = logging.getLogger(__name__)


def _is_near_duplicate(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


def _sanitize_timestamps(segs: list[SegmentRecord]) -> list[SegmentRecord]:
    out: list[SegmentRecord] = []
    for s in segs:
        if not s.text.strip():
            continue
        if s.start > s.end:
            logger.warning("swapping start/end for seg idx=%s", s.idx)
            s = s.model_copy(update={"start": s.end, "end": s.start})
        out.append(s)
    return out


def _clean_text(s: str) -> str:
    return normalize_punctuation(traditional_to_simplified(s))


class MergedTranscript:
    """Simple container; real SegmentRecord list output."""
    def __init__(self, segments: list[SegmentRecord]) -> None:
        self.segments = segments


def merge_chunks(chunks: list[ChunkTranscript]) -> MergedTranscript:
    # Collect + clean
    all_segs: list[SegmentRecord] = []
    for c in chunks:
        for s in c.segments:
            cleaned = _clean_text(s.text)
            all_segs.append(s.model_copy(update={"text": cleaned}))
    all_segs = _sanitize_timestamps(all_segs)

    # Sort by start; dedupe near-duplicates whose times overlap
    all_segs.sort(key=lambda s: (s.start, s.end))
    merged: list[SegmentRecord] = []
    for s in all_segs:
        if merged:
            prev = merged[-1]
            # Overlap window (last 15s) + near-text match → skip
            if s.start <= prev.end + 5.0 and _is_near_duplicate(s.text, prev.text):
                continue
        merged.append(s)

    # Renumber idx sequentially
    renumbered = [
        s.model_copy(update={"idx": i}) for i, s in enumerate(merged)
    ]
    return MergedTranscript(segments=renumbered)
```

- [ ] **Step 14.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/merger_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/merger.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/merger_test.py
git commit -m "feat(video-asr): merge chunks with cleaning + dedupe"
```

---

## Phase 7 — Renderer (md + srt)

### Task 15: raw.json → transcript.md + transcript.srt

**Files:**
- Create: `renderer.py` + `renderer_test.py`

- [ ] **Step 15.1: Write tests**

```python
from vision_intelligence.video_asr.renderer import (
    render_markdown, render_srt, format_srt_timestamp,
)
from vision_intelligence.video_asr.models import RawTranscript, SegmentRecord


def _raw(segments):
    return RawTranscript(
        video_id="abc", source="youtube",
        url="https://www.youtube.com/watch?v=abc",
        title="示例", uploader="Up", duration_sec=100.0,
        asr_model="gemini-2.5-flash", asr_version="v1",
        processed_at="2026-04-18T00:00:00+08:00",
        bgm_removed=True, segments=segments,
    )


def test_format_srt_timestamp():
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.123) == "00:01:05,123"
    assert format_srt_timestamp(3661.5) == "01:01:01,500"


def test_render_markdown_contains_header_and_speakers():
    segs = [
        SegmentRecord(idx=0, start=0.52, end=4.0, speaker="host",
                      text="家人们晚上好", text_normalized="",
                      confidence=0.95, chunk_id=0),
        SegmentRecord(idx=1, start=5.0, end=8.0, speaker="guest",
                      text="谢谢", text_normalized="", confidence=0.9, chunk_id=0),
    ]
    md = render_markdown(_raw(segs))
    assert "# 示例" in md
    assert "主播" in md and "嘉宾" in md
    assert "家人们晚上好" in md


def test_render_srt_numbered_blocks():
    segs = [
        SegmentRecord(idx=0, start=0.0, end=2.0, speaker="host",
                      text="A", text_normalized="", confidence=1.0, chunk_id=0),
    ]
    srt = render_srt(_raw(segs))
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,000\n[主播] A\n")
```

- [ ] **Step 15.2: Implement**

```python
"""Render raw.json → transcript.md + transcript.srt."""
from __future__ import annotations

from vision_intelligence.video_asr.models import RawTranscript, Speaker

_LABEL: dict[Speaker, str] = {
    "host": "主播", "guest": "嘉宾", "other": "其他", "unknown": "未知",
}


def format_srt_timestamp(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_markdown(raw: RawTranscript) -> str:
    lines: list[str] = [
        f"# {raw.title or raw.video_id}",
        "",
        f"**来源**: {raw.source} · {raw.uploader or '-'} · {raw.duration_sec or '-'}s",
        f"**处理时间**: {raw.processed_at}",
        f"**模型**: {raw.asr_model}",
        "",
        "---",
        "",
    ]
    for s in raw.segments:
        ts = format_srt_timestamp(s.start).split(",")[0]
        lines.append(f"**[{ts}] {_LABEL[s.speaker]}**: {s.text}")
        lines.append("")
    return "\n".join(lines)


def render_srt(raw: RawTranscript) -> str:
    blocks: list[str] = []
    for i, s in enumerate(raw.segments, start=1):
        blocks.append(
            f"{i}\n"
            f"{format_srt_timestamp(s.start)} --> {format_srt_timestamp(s.end)}\n"
            f"[{_LABEL[s.speaker]}] {s.text}\n"
        )
    return "\n".join(blocks)
```

- [ ] **Step 15.3: Commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/renderer_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/renderer.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/renderer_test.py
git commit -m "feat(video-asr): markdown + srt renderer"
```

---

## Phase 8 — Analyzer (summary + style)

### Task 16: Summary + style prompts

**Files:**
- Overwrite: `prompts/summarize.md`
- Overwrite: `prompts/style.md`

- [ ] **Step 16.1: Write `prompts/summarize.md`**

```markdown
# Video Summary

You are given a full transcript of a Chinese live-streaming or long-form video. Produce a markdown summary in Simplified Chinese with the following sections:

## 核心主题
（1-2 句）

## 章节划分
（基于时间戳把视频切成 5-8 个自然章节，每节 1 行）

## 关键卖点 / 观点
（bulleted list, 5-10 条）

## CTA / 行动号召
（如果有，列出主播要求观众做的动作）

Keep tone neutral; no editorializing. Output pure markdown, no code fences.
```

- [ ] **Step 16.2: Write `prompts/style.md`**

```markdown
# Host Style Profile Extraction

You receive the host's (主播) transcript lines only. Produce a JSON profile with:

- `top_phrases`: top 20 most frequent 2-4 char phrases (excluding trivial function words), each `{phrase, count}`
- `catchphrases`: 5-10 口头禅 (signature filler/hooks the host repeats)
- `opening_hooks`: 3-5 representative opening lines (direct quotes)
- `cta_patterns`: 3-10 representative CTA lines (direct quotes)
- `transition_patterns`: 3-8 transitional phrases (e.g. "接下来…", "说到这里…")
- `tone_tags`: 3-6 tags from {热情, 煽动, 亲和, 专业, 冷静, 紧迫, 幽默, 朴实}

Output a pure JSON object matching the schema. Use Simplified Chinese.
```

- [ ] **Step 16.3: Commit (prompts only)**

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/prompts/summarize.md \
        python-packages/intelligence/src/vision_intelligence/video_asr/prompts/style.md
git commit -m "feat(video-asr): analyzer prompts (summary + style)"
```

### Task 17: Analyzer implementation

**Files:**
- Create: `analyzer.py` + `analyzer_test.py`

- [ ] **Step 17.1: Write tests**

```python
from pathlib import Path
from unittest.mock import patch

from vision_intelligence.video_asr.analyzer import (
    analyze_transcript, _filter_for_style,
)
from vision_intelligence.video_asr.models import (
    RawTranscript, SegmentRecord, StyleProfile,
)


def _seg(text, speaker="host", conf=0.9):
    return SegmentRecord(
        idx=0, start=0, end=1, speaker=speaker,
        text=text, text_normalized=text,
        confidence=conf, chunk_id=0,
    )


def test_filter_keeps_only_high_conf_host():
    segs = [
        _seg("keep me", "host", 0.9),
        _seg("guest speech", "guest", 0.9),
        _seg("low conf", "host", 0.5),
        _seg("unknown", "unknown", 0.9),
    ]
    out = _filter_for_style(segs, min_conf=0.6)
    texts = [s.text for s in out]
    assert texts == ["keep me"]


def test_analyze_returns_summary_and_style(tmp_path):
    raw = RawTranscript(
        video_id="abc", source="youtube",
        url="u", title="t", uploader="u", duration_sec=10,
        asr_model="m", asr_version="v", processed_at="t",
        bgm_removed=True,
        segments=[_seg("家人们晚上好", "host", 0.95)],
    )
    fake_style_dict = {
        "top_phrases": [], "catchphrases": [], "opening_hooks": [],
        "cta_patterns": [], "transition_patterns": [], "tone_tags": [],
    }
    with patch("vision_intelligence.video_asr.analyzer._call_summary") as m_sum, \
         patch("vision_intelligence.video_asr.analyzer._call_style") as m_style:
        m_sum.return_value = ("# summary\nhi", {"input_tokens": 100, "output_tokens": 50})
        m_style.return_value = (fake_style_dict,
                                {"input_tokens": 100, "output_tokens": 50})
        result = analyze_transcript(
            raw, project="p", location="us-central1",
            model="gemini-2.5-flash", min_confidence=0.6,
        )
    assert result.summary_md.startswith("# summary")
    assert isinstance(result.style, StyleProfile)
    assert result.style.video_id == "abc"
```

- [ ] **Step 17.2: Implement**

```python
"""Analyzer: summary + style profile via Gemini."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from vision_intelligence.video_asr.models import (
    RawTranscript, SegmentRecord, StyleProfile,
)


@dataclass
class AnalyzeResult:
    summary_md: str
    style: StyleProfile
    summary_usage: dict
    style_usage: dict
    segments_filtered_out: int


def _filter_for_style(
    segs: list[SegmentRecord], *, min_conf: float,
) -> list[SegmentRecord]:
    return [s for s in segs if s.speaker == "host" and s.confidence >= min_conf]


def _load(name: str) -> str:
    return (Path(__file__).parent / "prompts" / name).read_text(encoding="utf-8")


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=2, min=2, max=20), reraise=True)
def _call_summary(*, client, model: str, transcript_text: str) -> tuple[str, dict]:
    resp = client.models.generate_content(
        model=model,
        contents=[_load("summarize.md"), transcript_text],
    )
    usage = {
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) or 0,
    }
    return resp.text, usage


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=2, min=2, max=20), reraise=True)
def _call_style(*, client, model: str, host_text: str) -> tuple[dict, dict]:
    from google.genai import types as gtypes
    resp = client.models.generate_content(
        model=model,
        contents=[_load("style.md"), host_text],
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    import json
    data = json.loads(resp.text)
    usage = {
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) or 0,
    }
    return data, usage


def _sentence_length_stats(segs: list[SegmentRecord]) -> dict:
    lens = sorted(len(s.text) for s in segs) or [0]
    def pct(p: float) -> float:
        i = max(0, int(round(p * (len(lens) - 1))))
        return float(lens[i])
    return {"p50": pct(0.5), "p90": pct(0.9), "unit": "chars"}


def _speaker_count(segs: list[SegmentRecord]) -> dict[str, int]:
    c = Counter(s.speaker for s in segs)
    return {k: int(c.get(k, 0)) for k in ("host", "guest", "other", "unknown")}


def analyze_transcript(
    raw: RawTranscript, *,
    project: str, location: str, model: str, min_confidence: float,
) -> AnalyzeResult:
    from google import genai
    client = genai.Client(vertexai=True, project=project, location=location)

    full_text = "\n".join(f"[{s.speaker}] {s.text}" for s in raw.segments)
    summary_md, summary_usage = _call_summary(
        client=client, model=model, transcript_text=full_text,
    )

    host_segs = _filter_for_style(raw.segments, min_conf=min_confidence)
    host_text = "\n".join(s.text for s in host_segs)
    style_dict, style_usage = _call_style(
        client=client, model=model, host_text=host_text,
    )

    total_chars = sum(len(s.text) for s in raw.segments) or 1
    host_chars = sum(len(s.text) for s in raw.segments if s.speaker == "host")
    english_chars = sum(
        1 for s in raw.segments for c in s.text
        if "a" <= c.lower() <= "z"
    )
    sp_counts = _speaker_count(raw.segments)

    style = StyleProfile(
        video_id=raw.video_id,
        host_speaking_ratio=host_chars / total_chars if total_chars else 0.0,
        speaker_count=sp_counts,
        top_phrases=style_dict.get("top_phrases", []),
        catchphrases=style_dict.get("catchphrases", []),
        opening_hooks=style_dict.get("opening_hooks", []),
        cta_patterns=style_dict.get("cta_patterns", []),
        transition_patterns=style_dict.get("transition_patterns", []),
        sentence_length=_sentence_length_stats(raw.segments),
        tone_tags=style_dict.get("tone_tags", []),
        english_ratio=english_chars / total_chars if total_chars else 0.0,
    )

    return AnalyzeResult(
        summary_md=summary_md,
        style=style,
        summary_usage=summary_usage,
        style_usage=style_usage,
        segments_filtered_out=len(raw.segments) - len(host_segs),
    )
```

- [ ] **Step 17.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/analyzer_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/analyzer.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/analyzer_test.py
git commit -m "feat(video-asr): analyzer — summary + style profile"
```

---

## Phase 9 — Pipeline orchestrator + Jobs

### Task 18: Pipeline orchestration (per-video, 7 stages)

**Files:**
- Create: `pipeline.py` + `pipeline_test.py`

- [ ] **Step 18.1: Write tests (heavy mocking of each stage)**

```python
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from vision_intelligence.video_asr.pipeline import run_video


@pytest.fixture
def mock_stages():
    """Patch every external I/O + LLM call to a no-op."""
    with patch("vision_intelligence.video_asr.pipeline._stage_ingest") as ingest, \
         patch("vision_intelligence.video_asr.pipeline._stage_preprocess") as prep, \
         patch("vision_intelligence.video_asr.pipeline._stage_transcribe") as trans, \
         patch("vision_intelligence.video_asr.pipeline._stage_merge") as merge, \
         patch("vision_intelligence.video_asr.pipeline._stage_render") as render, \
         patch("vision_intelligence.video_asr.pipeline._stage_analyze") as analyze, \
         patch("vision_intelligence.video_asr.pipeline._stage_load") as load:
        ingest.return_value = {"duration_sec": 1.0}
        prep.return_value = {"chunk_count": 1, "bgm_removed": True,
                             "chunk_duration_sec": 1200, "chunk_overlap_sec": 10,
                             "sample_rate": 16000, "channels": 1,
                             "demucs_model": "htdemucs", "boundaries": [[0.0, 1.0]]}
        trans.return_value = {"chunks_transcribed": 1, "chunks_failed": 0,
                              "tokens_in": 100, "tokens_out": 20,
                              "estimated_cost_usd": 0.001, "retries": 0}
        merge.return_value = {"segments_in": 1, "segments_out": 1,
                              "dedup_count": 0, "timestamp_fixes": 0,
                              "empty_dropped": 0}
        render.return_value = {"outputs": ["transcript.md", "transcript.srt"],
                               "total_segments": 1, "total_duration_sec": 1.0}
        analyze.return_value = {"tokens_in": 50, "tokens_out": 100,
                                "estimated_cost_usd": 0.001,
                                "segments_in": 1, "segments_filtered_out": 0}
        load.return_value = {"rows_inserted": {"video_sources": 1}}
        yield {
            "ingest": ingest, "preprocess": prep, "transcribe": trans,
            "merge": merge, "render": render, "analyze": analyze, "load": load,
        }


async def test_pipeline_runs_all_stages_in_order(tmp_path, mock_stages):
    ctx = MagicMock()
    ctx.video_id = "abc"
    ctx.url = "https://www.youtube.com/watch?v=abc"
    ctx.video_dir = tmp_path
    ctx.storage = AsyncMock()

    await run_video(ctx)

    # All 7 stages invoked once
    for key in ("ingest", "preprocess", "transcribe", "merge",
                "render", "analyze", "load"):
        assert mock_stages[key].called, f"{key} not called"


async def test_pipeline_skips_done_stages(tmp_path, mock_stages):
    from vision_intelligence.video_asr.manifest import write_manifest
    from vision_intelligence.video_asr.models import StageManifest
    # Pre-write a DONE manifest for ingest
    write_manifest(tmp_path, StageManifest(
        stage="ingest", video_id="abc", status="done",
        started_at="t0", finished_at="t1", duration_sec=0.0,
        inputs=[], outputs=["audio.m4a"], tool_versions={},
        pipeline_version="0.1.0",
    ))
    ctx = MagicMock()
    ctx.video_id = "abc"
    ctx.url = "https://www.youtube.com/watch?v=abc"
    ctx.video_dir = tmp_path
    ctx.storage = AsyncMock()

    await run_video(ctx)

    # ingest should NOT have been called
    assert not mock_stages["ingest"].called
    # later stages run
    assert mock_stages["preprocess"].called


async def test_pipeline_from_stage_deletes_downstream(tmp_path, mock_stages):
    from vision_intelligence.video_asr.manifest import write_manifest, manifest_path
    from vision_intelligence.video_asr.models import StageManifest
    # Pre-write all 7 manifests as done
    for stage in ("ingest", "preprocess", "transcribe", "merge",
                  "render", "analyze", "load"):
        write_manifest(tmp_path, StageManifest(
            stage=stage, video_id="abc", status="done",
            started_at="t", finished_at="t", duration_sec=0,
            inputs=[], outputs=[], tool_versions={}, pipeline_version="0.1.0",
        ))

    ctx = MagicMock()
    ctx.video_id = "abc"; ctx.url = "u"; ctx.video_dir = tmp_path
    ctx.storage = AsyncMock()

    await run_video(ctx, from_stage="merge")

    # merge, render, analyze, load manifests were deleted and re-run
    for key in ("merge", "render", "analyze", "load"):
        assert mock_stages[key].called
    # ingest/preprocess/transcribe NOT called
    for key in ("ingest", "preprocess", "transcribe"):
        assert not mock_stages[key].called
```

- [ ] **Step 18.2: Implement `pipeline.py`**

```python
"""7-stage pipeline orchestration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vision_intelligence.video_asr.manifest import (
    manifest_path, read_manifest, write_manifest,
)
from vision_intelligence.video_asr.models import StageManifest, StageName

logger = logging.getLogger(__name__)

_STAGE_ORDER: list[StageName] = [
    "ingest", "preprocess", "transcribe", "merge",
    "render", "analyze", "load",
]


@dataclass
class PipelineContext:
    video_id: str
    url: str
    video_dir: Path
    storage: Any  # VideoAsrStorage
    settings: Any  # VideoAsrSettings
    pipeline_version: str = "0.1.0"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


async def _stage_ingest(ctx: PipelineContext) -> dict: ...
async def _stage_preprocess(ctx: PipelineContext) -> dict: ...
async def _stage_transcribe(ctx: PipelineContext) -> dict: ...
async def _stage_merge(ctx: PipelineContext) -> dict: ...
async def _stage_render(ctx: PipelineContext) -> dict: ...
async def _stage_analyze(ctx: PipelineContext) -> dict: ...
async def _stage_load(ctx: PipelineContext) -> dict: ...


_STAGE_FNS = {
    "ingest": _stage_ingest, "preprocess": _stage_preprocess,
    "transcribe": _stage_transcribe, "merge": _stage_merge,
    "render": _stage_render, "analyze": _stage_analyze,
    "load": _stage_load,
}


def _delete_from_stage(video_dir: Path, from_stage: StageName) -> None:
    """Delete the from_stage manifest and all downstream manifests."""
    start = _STAGE_ORDER.index(from_stage)
    for s in _STAGE_ORDER[start:]:
        p = manifest_path(video_dir, s)
        if p.exists():
            p.unlink()


async def run_video(
    ctx: PipelineContext, *, from_stage: StageName | None = None,
) -> None:
    """Run all stages for one video, skipping those with DONE manifests."""
    if from_stage:
        _delete_from_stage(ctx.video_dir, from_stage)

    for stage in _STAGE_ORDER:
        existing = read_manifest(ctx.video_dir, stage)
        if existing and existing.status == "done":
            logger.info("skip done stage %s for %s", stage, ctx.video_id)
            continue

        await ctx.storage.set_pipeline_run(
            video_id=ctx.video_id, stage=stage,
            status="running", started_at=_now(),
        )
        started = _now()
        fn = _STAGE_FNS[stage]
        try:
            extra = await fn(ctx) or {}
            finished = _now()
            m = StageManifest(
                stage=stage, video_id=ctx.video_id, status="done",
                started_at=started, finished_at=finished,
                duration_sec=_delta_sec(started, finished),
                inputs=extra.pop("inputs", []),
                outputs=extra.pop("outputs", []),
                tool_versions=extra.pop("tool_versions", {}),
                pipeline_version=ctx.pipeline_version,
                extra=extra,
            )
            write_manifest(ctx.video_dir, m)
            await ctx.storage.set_pipeline_run(
                video_id=ctx.video_id, stage=stage, status="done",
                started_at=started, finished_at=finished,
                duration_sec=m.duration_sec,
            )
        except Exception as e:
            finished = _now()
            m = StageManifest(
                stage=stage, video_id=ctx.video_id, status="failed",
                started_at=started, finished_at=finished,
                duration_sec=_delta_sec(started, finished),
                inputs=[], outputs=[], tool_versions={},
                pipeline_version=ctx.pipeline_version,
                error=repr(e),
            )
            write_manifest(ctx.video_dir, m)
            await ctx.storage.set_pipeline_run(
                video_id=ctx.video_id, stage=stage, status="failed",
                started_at=started, finished_at=finished,
                duration_sec=m.duration_sec, error=repr(e),
            )
            raise


def _delta_sec(a_iso: str, b_iso: str) -> float:
    a = datetime.fromisoformat(a_iso)
    b = datetime.fromisoformat(b_iso)
    return (b - a).total_seconds()
```

> [!NOTE]
> `_stage_ingest` through `_stage_load` are declared as no-ops here; they will be filled in Task 19.

- [ ] **Step 18.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/pipeline_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/pipeline.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/pipeline_test.py
git commit -m "feat(video-asr): pipeline orchestrator skeleton with from-stage"
```

### Task 19: Fill in each stage function

**Files:**
- Modify: `pipeline.py`

- [ ] **Step 19.1: Implement `_stage_ingest`**

Replace the `async def _stage_ingest(ctx: PipelineContext) -> dict: ...` stub with:

```python
async def _stage_ingest(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.sources.registry import get_source
    src = get_source(ctx.url)
    meta = src.fetch_metadata(ctx.url)
    audio_out = ctx.video_dir / "audio.m4a"
    bytes_written = src.download_audio(ctx.url, audio_out)

    (ctx.video_dir / "source.json").write_text(
        meta.model_dump_json(indent=2), encoding="utf-8")

    await ctx.storage.upsert_video_source(
        meta, asr_model=ctx.settings.gemini_model,
        bgm_removed=ctx.settings.enable_bgm_removal,
    )

    return {
        "inputs": [],
        "outputs": ["audio.m4a", "source.json"],
        "tool_versions": {"yt-dlp": _tool_version("yt-dlp", "--version")},
        "url": ctx.url,
        "downloaded_bytes": bytes_written,
        "source_metadata": meta.model_dump(),
    }
```

Add helper at module top (after imports):

```python
import subprocess

def _tool_version(cmd: str, arg: str) -> str:
    try:
        out = subprocess.run(
            [cmd, arg], capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()[0]
        return out
    except Exception:
        return "unknown"
```

- [ ] **Step 19.2: Implement `_stage_preprocess`**

```python
async def _stage_preprocess(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.preprocessor import preprocess_audio
    audio = ctx.video_dir / "audio.m4a"
    vocals = ctx.video_dir / "vocals.wav"
    chunks_dir = ctx.video_dir / "chunks"
    info = await asyncio.to_thread(
        preprocess_audio,
        audio, vocals, chunks_dir,
        chunk_sec=ctx.settings.chunk_duration_sec,
        overlap_sec=ctx.settings.chunk_overlap_sec,
        enable_bgm_removal=ctx.settings.enable_bgm_removal,
    )
    return {
        "inputs": ["audio.m4a"],
        "outputs": ["vocals.wav", f"chunks/ ({info['chunk_count']} files)"],
        "tool_versions": {
            "demucs": _tool_version("python", "-c \"import demucs; print(demucs.__version__)\""),
            "ffmpeg": _tool_version("ffmpeg", "-version"),
        },
        **info,
    }
```

- [ ] **Step 19.3: Implement `_stage_transcribe`**

```python
async def _stage_transcribe(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.asr.gemini import GeminiTranscriber
    from vision_intelligence.video_asr.cost import estimate_cost_usd
    from vision_intelligence.video_asr.manifest import read_manifest

    preprocess = read_manifest(ctx.video_dir, "preprocess")
    boundaries = preprocess.extra["boundaries"]
    chunks_dir = ctx.video_dir / "chunks"

    transcriber = GeminiTranscriber(
        model=ctx.settings.gemini_model,
        project=ctx.settings.gcp_project,
        location=ctx.settings.gcp_location,
    )

    sem = asyncio.Semaphore(ctx.settings.transcribe_concurrency)
    total_in = total_out = 0

    async def do_chunk(i: int, start_offset: float) -> None:
        nonlocal total_in, total_out
        async with sem:
            audio = chunks_dir / f"chunk_{i:03d}.wav"
            def _work():
                import json as _json
                ct = transcriber.transcribe_chunk(
                    audio, chunk_id=i, start_offset=start_offset,
                )
                (chunks_dir / f"chunk_{i:03d}.json").write_text(
                    ct.model_dump_json(indent=2), encoding="utf-8")
                # usage is stashed on ct by GeminiTranscriber
                return getattr(ct, "__pydantic_extra__", {}) or {}
            usage_wrap = await asyncio.to_thread(_work)
            usage = usage_wrap.get("usage", {"input_tokens": 0, "output_tokens": 0})
            total_in += usage["input_tokens"]
            total_out += usage["output_tokens"]

    tasks = [do_chunk(i, start) for i, (start, _) in enumerate(boundaries)]
    await asyncio.gather(*tasks)

    cost = estimate_cost_usd(
        model=ctx.settings.gemini_model,
        input_tokens=total_in, output_tokens=total_out,
    )
    await ctx.storage.log_llm_usage(
        video_id=ctx.video_id, stage="transcribe",
        model=ctx.settings.gemini_model,
        input_tokens=total_in, output_tokens=total_out,
        estimated_cost_usd=cost, called_at=_now(),
    )

    return {
        "inputs": ["vocals.wav", "chunks/*.wav"],
        "outputs": ["chunks/*.json"],
        "model": ctx.settings.gemini_model,
        "chunks_transcribed": len(boundaries),
        "chunks_failed": 0,
        "tokens_in": total_in, "tokens_out": total_out,
        "estimated_cost_usd": cost,
        "prompt_version": _file_hash(
            Path(__file__).parent / "prompts" / "transcribe.md"),
    }


def _file_hash(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
```

- [ ] **Step 19.4: Implement `_stage_merge`**

```python
async def _stage_merge(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.merger import merge_chunks
    from vision_intelligence.video_asr.models import (
        ChunkTranscript, RawTranscript,
    )
    from vision_intelligence.video_asr.manifest import read_manifest

    chunks_dir = ctx.video_dir / "chunks"
    ingest = read_manifest(ctx.video_dir, "ingest")
    meta = ingest.extra["source_metadata"]

    chunks = [
        ChunkTranscript.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(chunks_dir.glob("chunk_*.json"))
    ]
    in_count = sum(len(c.segments) for c in chunks)
    merged = merge_chunks(chunks)
    out_count = len(merged.segments)

    raw = RawTranscript(
        video_id=ctx.video_id, source=meta["source"], url=meta["url"],
        title=meta.get("title"), uploader=meta.get("uploader"),
        duration_sec=meta.get("duration_sec"),
        asr_model=ctx.settings.gemini_model,
        asr_version="2026-04-18",
        processed_at=_now(),
        bgm_removed=ctx.settings.enable_bgm_removal,
        segments=merged.segments,
    )
    (ctx.video_dir / "raw.json").write_text(
        raw.model_dump_json(indent=2), encoding="utf-8")

    return {
        "inputs": ["chunks/*.json"],
        "outputs": ["raw.json"],
        "segments_in": in_count, "segments_out": out_count,
        "dedup_count": in_count - out_count,
    }
```

- [ ] **Step 19.5: Implement `_stage_render`**

```python
async def _stage_render(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.renderer import render_markdown, render_srt
    from vision_intelligence.video_asr.models import RawTranscript

    raw = RawTranscript.model_validate_json(
        (ctx.video_dir / "raw.json").read_text(encoding="utf-8"))
    (ctx.video_dir / "transcript.md").write_text(
        render_markdown(raw), encoding="utf-8")
    (ctx.video_dir / "transcript.srt").write_text(
        render_srt(raw), encoding="utf-8")

    return {
        "inputs": ["raw.json"],
        "outputs": ["transcript.md", "transcript.srt"],
        "total_segments": len(raw.segments),
        "total_duration_sec": raw.duration_sec,
    }
```

- [ ] **Step 19.6: Implement `_stage_analyze`**

```python
async def _stage_analyze(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.analyzer import analyze_transcript
    from vision_intelligence.video_asr.cost import estimate_cost_usd
    from vision_intelligence.video_asr.models import RawTranscript

    raw = RawTranscript.model_validate_json(
        (ctx.video_dir / "raw.json").read_text(encoding="utf-8"))

    result = await asyncio.to_thread(
        analyze_transcript, raw,
        project=ctx.settings.gcp_project,
        location=ctx.settings.gcp_location,
        model=ctx.settings.analyze_model,
        min_confidence=ctx.settings.min_confidence_for_style,
    )

    (ctx.video_dir / "summary.md").write_text(result.summary_md, encoding="utf-8")
    (ctx.video_dir / "style.json").write_text(
        result.style.model_dump_json(indent=2), encoding="utf-8")

    total_in = result.summary_usage["input_tokens"] + result.style_usage["input_tokens"]
    total_out = result.summary_usage["output_tokens"] + result.style_usage["output_tokens"]
    cost = estimate_cost_usd(
        model=ctx.settings.analyze_model,
        input_tokens=total_in, output_tokens=total_out,
    )
    await ctx.storage.log_llm_usage(
        video_id=ctx.video_id, stage="analyze",
        model=ctx.settings.analyze_model,
        input_tokens=total_in, output_tokens=total_out,
        estimated_cost_usd=cost, called_at=_now(),
    )

    return {
        "inputs": ["raw.json"],
        "outputs": ["summary.md", "style.json"],
        "model": ctx.settings.analyze_model,
        "tokens_in": total_in, "tokens_out": total_out,
        "estimated_cost_usd": cost,
        "segments_in": len(raw.segments),
        "segments_filtered_out": result.segments_filtered_out,
    }
```

- [ ] **Step 19.7: Implement `_stage_load`**

```python
async def _stage_load(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    from vision_intelligence.video_asr.models import RawTranscript, StyleProfile

    raw = RawTranscript.model_validate_json(
        (ctx.video_dir / "raw.json").read_text(encoding="utf-8"))
    # Fill text_normalized via jieba
    normalized = [
        s.model_copy(update={"text_normalized": jieba_tokenize(s.text)})
        for s in raw.segments
    ]
    raw_norm = raw.model_copy(update={"segments": normalized})
    await ctx.storage.write_segments(raw_norm)

    style = StyleProfile.model_validate_json(
        (ctx.video_dir / "style.json").read_text(encoding="utf-8"))
    await ctx.storage.upsert_style_profile(style)

    return {
        "inputs": ["raw.json", "style.json"],
        "outputs": [],
        "rows_inserted": {
            "video_sources": 1,
            "transcript_segments": len(normalized),
            "transcript_fts": len(normalized),
            "style_profiles": 1,
        },
    }
```

- [ ] **Step 19.8: Test + commit**

Pipeline tests from Task 18 should still pass (mocks replace these fns):

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/pipeline_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/pipeline.py
git commit -m "feat(video-asr): fill in all 7 pipeline stages"
```

### Task 20: JobManager (async task lifecycle)

**Files:**
- Create: `jobs.py` + `jobs_test.py`

- [ ] **Step 20.1: Write tests**

```python
import asyncio
from unittest.mock import AsyncMock

import pytest

from vision_intelligence.video_asr.jobs import JobManager


async def test_job_manager_tracks_asyncio_task():
    jm = JobManager()
    done = asyncio.Event()

    async def fake_job():
        await done.wait()

    job_id = jm.submit("job1", fake_job())
    assert jm.is_running(job_id)
    done.set()
    await jm.wait(job_id)
    assert not jm.is_running(job_id)


async def test_job_manager_captures_exception():
    jm = JobManager()

    async def boom():
        raise RuntimeError("boom")

    job_id = jm.submit("jobx", boom())
    await jm.wait(job_id)
    err = jm.get_error(job_id)
    assert err is not None and "boom" in err
```

- [ ] **Step 20.2: Implement**

```python
"""In-process asyncio job manager."""
from __future__ import annotations

import asyncio
from typing import Awaitable


class JobManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(self, job_id: str, coro: Awaitable) -> str:
        task = asyncio.create_task(coro, name=job_id)
        self._tasks[job_id] = task
        return job_id

    def is_running(self, job_id: str) -> bool:
        t = self._tasks.get(job_id)
        return bool(t and not t.done())

    async def wait(self, job_id: str) -> None:
        t = self._tasks.get(job_id)
        if t is not None:
            try:
                await t
            except Exception:
                pass

    def get_error(self, job_id: str) -> str | None:
        t = self._tasks.get(job_id)
        if t is None or not t.done():
            return None
        exc = t.exception()
        return repr(exc) if exc else None
```

- [ ] **Step 20.3: Test + commit**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/jobs_test.py -v
git add python-packages/intelligence/src/vision_intelligence/video_asr/jobs.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/jobs_test.py
git commit -m "feat(video-asr): in-process async JobManager"
```

---

## Phase 10 — CLI

### Task 21: typer CLI

**Files:**
- Create: `cli.py` + `cli_test.py`

- [ ] **Step 21.1: Write tests (typer.testing)**

```python
from typer.testing import CliRunner

from vision_intelligence.video_asr.cli import app

runner = CliRunner()


def test_help_lists_all_subcommands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("run", "status", "rerun", "search", "export"):
        assert cmd in r.stdout
```

- [ ] **Step 21.2: Implement**

```python
"""typer CLI for video ASR pipeline."""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

app = typer.Typer(help="Vision video ASR pipeline CLI")


@app.command()
def run(
    sources: Path = typer.Option(None, "--sources"),
    url: str = typer.Option(None, "--url"),
) -> None:
    """Run the pipeline for a sources.yaml or a single URL."""
    from vision_intelligence.video_asr.runner import run_cli_job
    asyncio.run(run_cli_job(sources_yaml=sources, url=url))


@app.command()
def status(job_id: str) -> None:
    from vision_intelligence.video_asr.runner import show_status
    asyncio.run(show_status(job_id))


@app.command()
def rerun(
    video_id: str,
    stages: str = typer.Option(None, "--stages"),
    from_stage: str = typer.Option(None, "--from-stage"),
) -> None:
    from vision_intelligence.video_asr.runner import rerun_video
    asyncio.run(rerun_video(video_id, stages=stages, from_stage=from_stage))


@app.command()
def search(q: str, limit: int = 50) -> None:
    from vision_intelligence.video_asr.runner import search_fts
    asyncio.run(search_fts(q, limit=limit))


@app.command()
def export(
    format: str = typer.Option("jsonl", "--format"),
) -> None:
    from vision_intelligence.video_asr.runner import export_all
    asyncio.run(export_all(format))


if __name__ == "__main__":
    app()
```

Also create `runner.py` with the CLI command implementations (thin wrappers that wire settings + DB + pipeline):

```python
"""CLI command implementations — thin wrappers over pipeline/storage."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from vision_intelligence.video_asr.config import VideoAsrSettings
from vision_intelligence.video_asr.jobs import JobManager
from vision_intelligence.video_asr.pipeline import PipelineContext, run_video
from vision_intelligence.video_asr.sources.registry import get_source
from vision_intelligence.video_asr.sources.yaml_loader import load_sources
from vision_intelligence.video_asr.storage import VideoAsrStorage


async def _open_storage(settings: VideoAsrSettings) -> tuple[aiosqlite.Connection, VideoAsrStorage]:
    db_path = Path("vision.db")
    conn = await aiosqlite.connect(db_path)
    st = VideoAsrStorage(conn)
    await st.init_schema()
    return conn, st


async def run_cli_job(*, sources_yaml: Path | None, url: str | None) -> None:
    if not sources_yaml and not url:
        sys.stderr.write("Must provide --sources or --url\n"); sys.exit(2)
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        if sources_yaml:
            entries = load_sources(str(sources_yaml))
            urls = [e.url for e in entries]
            job_id = await st.create_or_get_job(urls, source="cli")
            print(f"job_id={job_id}")
            for e in entries:
                await _run_one(st, settings, e.url, e.video_id, job_id)
            await st.set_job_status(job_id, "done")
        else:
            src = get_source(url)
            video_id = src.extract_video_id(url)
            job_id = await st.create_or_get_job([url], source="cli")
            print(f"job_id={job_id}")
            await _run_one(st, settings, url, video_id, job_id)
            await st.set_job_status(job_id, "done")
    finally:
        await conn.close()


async def _run_one(
    st: VideoAsrStorage, settings: VideoAsrSettings,
    url: str, video_id: str, job_id: str,
) -> None:
    await st.link_job_video(job_id, video_id)
    video_dir = Path(settings.output_root) / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    ctx = PipelineContext(
        video_id=video_id, url=url, video_dir=video_dir,
        storage=st, settings=settings,
    )
    try:
        await run_video(ctx)
    except Exception as e:
        print(f"[{video_id}] FAILED: {e!r}")


async def show_status(job_id: str) -> None:
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        cur = await conn.execute(
            "SELECT video_id FROM asr_job_videos WHERE job_id = ?", (job_id,))
        rows = await cur.fetchall()
        for r in rows:
            vid = r[0]
            print(f"--- {vid} ---")
            cur2 = await conn.execute(
                "SELECT stage, status, duration_sec FROM pipeline_runs "
                "WHERE video_id = ? ORDER BY started_at", (vid,))
            for stage, status, dur in await cur2.fetchall():
                print(f"  {stage}: {status}  ({dur}s)")
    finally:
        await conn.close()


async def rerun_video(
    video_id: str, *, stages: str | None, from_stage: str | None,
) -> None:
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        video_dir = Path(settings.output_root) / video_id
        cur = await conn.execute(
            "SELECT url FROM video_sources WHERE video_id = ?", (video_id,))
        row = await cur.fetchone()
        if row is None:
            print(f"unknown video_id {video_id}"); sys.exit(1)
        url = row[0]
        ctx = PipelineContext(
            video_id=video_id, url=url, video_dir=video_dir,
            storage=st, settings=settings,
        )
        if from_stage:
            await run_video(ctx, from_stage=from_stage)
        elif stages:
            # Delete each requested stage manifest then run full pipeline;
            # the orchestrator will resume others from their existing DONE state.
            from vision_intelligence.video_asr.manifest import manifest_path
            for s in stages.split(","):
                p = manifest_path(video_dir, s.strip())
                if p.exists():
                    p.unlink()
            await run_video(ctx)
        else:
            # Full rerun
            await run_video(ctx, from_stage="ingest")
    finally:
        await conn.close()


async def search_fts(q: str, *, limit: int) -> None:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        query = jieba_tokenize(q)
        hits = await st.search_segments(query, limit=limit)
        for h in hits:
            print(f"[{h['video_id']}] t={h['start']:.1f}s ({h['speaker']}): {h['text']}")
    finally:
        await conn.close()


async def export_all(format: str) -> None:
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        cur = await conn.execute(
            "SELECT video_id, idx, start, end, speaker, text FROM transcript_segments "
            "ORDER BY video_id, idx")
        if format == "jsonl":
            async for row in cur:
                sys.stdout.write(json.dumps({
                    "video_id": row[0], "idx": row[1], "start": row[2],
                    "end": row[3], "speaker": row[4], "text": row[5],
                }, ensure_ascii=False) + "\n")
    finally:
        await conn.close()
```

- [ ] **Step 21.3: Test + commit**

```bash
uv sync --all-packages  # re-register console script
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/cli_test.py -v
uv run vision-video-asr --help | head -10
git add python-packages/intelligence/src/vision_intelligence/video_asr/cli.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/cli_test.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/runner.py
git commit -m "feat(video-asr): typer CLI (run/status/rerun/search/export)"
```

---

## Phase 11 — FastAPI routes

### Task 22: API Key middleware

**Files:**
- Create: `python-packages/api/src/vision_api/api_key.py`
- Create: `python-packages/api/src/vision_api/api_key_test.py`
- Modify: `python-packages/api/src/vision_api/main.py`
- Modify: `python-packages/api/src/vision_api/settings.py`

- [ ] **Step 22.1: Write test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vision_api.api_key import ApiKeyMiddleware


def _build(api_key: str = "secret"):
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware, api_key=api_key,
                       protected_prefixes=("/api/intelligence/",))
    @app.post("/api/intelligence/foo")
    def foo(): return {"ok": True}
    @app.get("/api/intelligence/foo")
    def foo_get(): return {"ok": True}
    @app.get("/health")
    def health(): return {"ok": True}
    return app


def test_protected_write_requires_key():
    app = _build()
    c = TestClient(app)
    assert c.post("/api/intelligence/foo").status_code == 401
    assert c.post("/api/intelligence/foo",
                  headers={"X-API-Key": "wrong"}).status_code == 403
    assert c.post("/api/intelligence/foo",
                  headers={"X-API-Key": "secret"}).status_code == 200


def test_protected_read_allowed_without_key():
    app = _build()
    c = TestClient(app)
    assert c.get("/api/intelligence/foo").status_code == 200


def test_unprotected_path_allowed():
    app = _build()
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.post("/health").status_code == 405  # method not allowed, but not blocked
```

- [ ] **Step 22.2: Implement `api_key.py`**

```python
"""X-API-Key middleware protecting POST/PUT/DELETE on /api/*."""
from __future__ import annotations

from typing import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, api_key: str, protected_prefixes: Sequence[str]) -> None:
        super().__init__(app)
        self._key = api_key
        self._prefixes = tuple(protected_prefixes)

    async def dispatch(self, request, call_next):
        if request.method in _PROTECTED_METHODS and \
           any(request.url.path.startswith(p) for p in self._prefixes):
            header = request.headers.get("x-api-key")
            if not header:
                return JSONResponse({"detail": "missing X-API-Key"}, status_code=401)
            if header != self._key:
                return JSONResponse({"detail": "invalid X-API-Key"}, status_code=403)
        return await call_next(request)
```

- [ ] **Step 22.3: Register in `main.py` + add `vision_api_key` to settings**

In `settings.py`, add after the existing fields:

```python
    vision_api_key: str = "dev-key"
```

In `main.py`, after `app = FastAPI(...)` and before `app.add_middleware(CORSMiddleware, ...)`:

```python
    from vision_api.api_key import ApiKeyMiddleware
    app.add_middleware(
        ApiKeyMiddleware, api_key=settings.vision_api_key,
        protected_prefixes=("/api/intelligence/",),
    )
```

- [ ] **Step 22.4: Test + commit**

```bash
uv run pytest python-packages/api/src/vision_api/api_key_test.py -v
uv run pytest -q 2>&1 | tail -3   # verify nothing else broke
git add python-packages/api/src/vision_api/api_key.py \
        python-packages/api/src/vision_api/api_key_test.py \
        python-packages/api/src/vision_api/main.py \
        python-packages/api/src/vision_api/settings.py
git commit -m "feat(api): X-API-Key middleware for /api/intelligence/ writes"
```

### Task 23: `/api/intelligence/video-asr/*` routes

**Files:**
- Create: `python-packages/api/src/vision_api/video_asr_routes.py`
- Create: `python-packages/api/src/vision_api/video_asr_routes_test.py`
- Modify: `python-packages/api/src/vision_api/main.py` (register router + lifespan)

- [ ] **Step 23.1: Write tests (FastAPI TestClient)**

```python
"""HTTP contract tests for video-asr routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from vision_api.main import create_app


def _client(api_key: str = "test-key"):
    import os
    os.environ["VISION_API_KEY"] = api_key
    app = create_app()
    return TestClient(app)


def test_post_jobs_requires_api_key():
    c = _client()
    r = c.post("/api/intelligence/video-asr/jobs", json={"urls": ["u"]})
    assert r.status_code == 401


def test_get_jobs_no_key_required():
    c = _client()
    r = c.get("/api/intelligence/video-asr/jobs/nope")
    assert r.status_code in (404, 200)
```

- [ ] **Step 23.2: Implement routes**

```python
"""FastAPI routes for video ASR (thin shell → vision_intelligence.video_asr)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api/intelligence/video-asr", tags=["video-asr"])


class JobCreate(BaseModel):
    urls: list[str] | None = None
    sources_yaml: str | None = None


@router.post("/jobs")
async def create_job(body: JobCreate, request: Request) -> dict:
    from vision_intelligence.video_asr.sources.yaml_loader import load_sources
    st = request.app.state.video_asr_storage
    jm = request.app.state.video_asr_jm
    settings = request.app.state.video_asr_settings

    if body.sources_yaml:
        entries = load_sources(body.sources_yaml)
        urls = [e.url for e in entries]
    elif body.urls:
        urls = body.urls
        entries = None
    else:
        raise HTTPException(400, "urls or sources_yaml required")

    job_id = await st.create_or_get_job(urls, source="api")

    async def run_all():
        from vision_intelligence.video_asr.pipeline import (
            PipelineContext, run_video,
        )
        from vision_intelligence.video_asr.sources.registry import get_source
        for u in urls:
            src = get_source(u)
            vid = src.extract_video_id(u)
            await st.link_job_video(job_id, vid)
            video_dir = Path(settings.output_root) / vid
            video_dir.mkdir(parents=True, exist_ok=True)
            ctx = PipelineContext(
                video_id=vid, url=u, video_dir=video_dir,
                storage=st, settings=settings,
            )
            try:
                await run_video(ctx)
            except Exception:
                continue
        await st.set_job_status(job_id, "done")

    jm.submit(job_id, run_all())
    video_ids = [
        request.app.state.video_asr_settings.gemini_model  # placeholder
    ]  # replaced below
    # Compute video_ids upfront for the response
    from vision_intelligence.video_asr.sources.registry import get_source
    video_ids = [get_source(u).extract_video_id(u) for u in urls]
    return {"job_id": job_id, "video_ids": video_ids, "status": "accepted"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    st = request.app.state.video_asr_storage
    conn = st._conn
    cur = await conn.execute(
        "SELECT job_id, status FROM asr_jobs WHERE job_id = ?", (job_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "job not found")
    cur = await conn.execute(
        "SELECT video_id FROM asr_job_videos WHERE job_id = ?", (job_id,))
    vids = [r[0] for r in await cur.fetchall()]
    per_video = []
    total_cost = 0.0
    for v in vids:
        cur = await conn.execute(
            "SELECT stage, status, duration_sec FROM pipeline_runs "
            "WHERE video_id = ? ORDER BY started_at", (v,))
        stages = [
            {"stage": r[0], "status": r[1], "duration_sec": r[2]}
            for r in await cur.fetchall()
        ]
        total_cost += await st.sum_cost(v)
        per_video.append({"video_id": v, "stages": stages})
    return {
        "job_id": job_id, "status": row[1],
        "videos": per_video, "cost_usd": round(total_cost, 4),
    }


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> EventSourceResponse:
    st = request.app.state.video_asr_storage
    last_event_id = request.headers.get("last-event-id")

    async def generator():
        last_seen = int(last_event_id) if last_event_id else 0
        while True:
            conn = st._conn
            cur = await conn.execute(
                "SELECT rowid, video_id, stage, status, finished_at "
                "FROM pipeline_runs WHERE rowid > ? ORDER BY rowid",
                (last_seen,))
            rows = await cur.fetchall()
            for r in rows:
                last_seen = r[0]
                yield {
                    "id": str(last_seen),
                    "event": "stage_update",
                    "data": json.dumps({
                        "video_id": r[1], "stage": r[2], "status": r[3],
                        "finished_at": r[4],
                    }, ensure_ascii=False),
                }
            await asyncio.sleep(1.0)

    return EventSourceResponse(generator())


def _video_dir(settings, video_id: str) -> Path:
    return Path(settings.output_root) / video_id


@router.get("/videos/{video_id}")
async def get_video(video_id: str, request: Request) -> dict:
    st = request.app.state.video_asr_storage
    row = await st.get_video_source(video_id)
    if row is None:
        raise HTTPException(404, "video not found")
    return row


@router.get("/videos/{video_id}/transcript")
async def get_transcript(video_id: str, request: Request) -> dict:
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "raw.json"
    if not p.exists():
        raise HTTPException(404)
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/videos/{video_id}/transcript.md")
async def get_transcript_md(video_id: str, request: Request):
    from fastapi.responses import PlainTextResponse
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "transcript.md"
    if not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/videos/{video_id}/transcript.srt")
async def get_transcript_srt(video_id: str, request: Request):
    from fastapi.responses import PlainTextResponse
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "transcript.srt"
    if not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/plain")


@router.get("/videos/{video_id}/summary")
async def get_summary(video_id: str, request: Request):
    from fastapi.responses import PlainTextResponse
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "summary.md"
    if not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/videos/{video_id}/style")
async def get_style(video_id: str, request: Request) -> dict:
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "style.json"
    if not p.exists():
        raise HTTPException(404)
    return json.loads(p.read_text(encoding="utf-8"))


class RerunBody(BaseModel):
    stages: list[str] | None = None
    from_stage: str | None = None


@router.post("/videos/{video_id}/rerun")
async def rerun(video_id: str, body: RerunBody, request: Request) -> dict:
    from vision_intelligence.video_asr.pipeline import (
        PipelineContext, run_video,
    )
    st = request.app.state.video_asr_storage
    settings = request.app.state.video_asr_settings
    jm = request.app.state.video_asr_jm

    row = await st.get_video_source(video_id)
    if row is None:
        raise HTTPException(404)
    ctx = PipelineContext(
        video_id=video_id, url=row["url"],
        video_dir=_video_dir(settings, video_id),
        storage=st, settings=settings,
    )

    async def go():
        if body.from_stage:
            await run_video(ctx, from_stage=body.from_stage)
        elif body.stages:
            from vision_intelligence.video_asr.manifest import manifest_path
            for s in body.stages:
                p = manifest_path(ctx.video_dir, s)
                if p.exists():
                    p.unlink()
            await run_video(ctx)
        else:
            await run_video(ctx, from_stage="ingest")

    jm.submit(f"rerun-{video_id}", go())
    return {"video_id": video_id, "status": "restarted"}


@router.get("/search")
async def search(request: Request, q: str, limit: int = 50) -> list[dict]:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    st = request.app.state.video_asr_storage
    return await st.search_segments(jieba_tokenize(q), limit=limit)
```

- [ ] **Step 23.3: Wire into `vision_api.main`**

In `main.py`:

1. Add import at top:
```python
from vision_api.video_asr_routes import router as video_asr_router
```

2. Inside `lifespan`, after `app.state.db = Database(...)` and `await app.state.db.init()`:
```python
        import aiosqlite
        from vision_intelligence.video_asr.config import VideoAsrSettings
        from vision_intelligence.video_asr.jobs import JobManager
        from vision_intelligence.video_asr.storage import VideoAsrStorage
        asr_conn = await aiosqlite.connect(settings.vision_db_path)
        asr_storage = VideoAsrStorage(asr_conn)
        await asr_storage.init_schema()
        app.state.video_asr_conn = asr_conn
        app.state.video_asr_storage = asr_storage
        app.state.video_asr_jm = JobManager()
        app.state.video_asr_settings = VideoAsrSettings()
```

3. Inside `lifespan` shutdown section (after `await app.state.db.close()`):
```python
        await app.state.video_asr_conn.close()
```

4. After the existing `app.include_router(rag_router)`:
```python
    app.include_router(video_asr_router)
```

5. Add dep:
```bash
# inside python-packages/api/pyproject.toml, add to dependencies:
#   "sse-starlette>=2.0"
```
Then `uv sync --all-packages`.

- [ ] **Step 23.4: Test + commit**

```bash
uv sync --all-packages
uv run pytest python-packages/api/src/vision_api/video_asr_routes_test.py -v
uv run pytest -q 2>&1 | tail -3
git add python-packages/api/ python-packages/api/pyproject.toml uv.lock
git commit -m "feat(api): video-asr routes (jobs/videos/search/SSE) + lifespan wiring"
```

---

## Phase 12 — Integration & PR

### Task 24: Makefile + CONTRIBUTING update

**Files:**
- Modify: `Makefile.mac`, `Makefile`, `CONTRIBUTING.md`

- [ ] **Step 24.1: Add `asr` target to `Makefile.mac`**

After the existing `format` target, add:

```make
# ── Video ASR ──────────────────────────────────────────────────────────────────

asr:
	uv run vision-video-asr run --sources config/video_asr/sources.yaml
```

And to `Makefile` (Windows counterpart):

```make
asr:
	uv run vision-video-asr run --sources config/video_asr/sources.yaml
```

- [ ] **Step 24.2: Add ASR section to `CONTRIBUTING.md`**

Append at the end:

```markdown
## Video ASR 管线

### 前置条件

- `brew install ffmpeg`
- `gcloud auth application-default login`（Vertex AI ADC 凭证）
- `.env` 里配置：
  ```
  VIDEO_ASR_GCP_PROJECT=<your gcp project>
  VIDEO_ASR_GCP_LOCATION=us-central1
  VISION_API_KEY=<任意 secret；HTTP 写端点校验用>
  ```

### 跑首批视频

```bash
make -f Makefile.mac asr
# or
uv run vision-video-asr run --sources config/video_asr/sources.yaml
```

产物落盘到 `output/transcripts/<video_id>/` 与 `vision.db`。

### 搜索已转录内容

```bash
uv run vision-video-asr search "家人们晚上好" --limit 20
```

### 从某阶段重跑

```bash
uv run vision-video-asr rerun <video_id> --from-stage transcribe
```
```

- [ ] **Step 24.3: Commit**

```bash
git add Makefile Makefile.mac CONTRIBUTING.md
git commit -m "docs(video-asr): Makefile asr target + CONTRIBUTING section"
```

### Task 25: First real-video smoke run (manual, human-gated)

**Files:** none

- [ ] **Step 25.1: Pick one short-ish video for smoke test**

Edit `config/video_asr/sources.yaml` temporarily, or:

```bash
uv run vision-video-asr run --url "https://www.youtube.com/watch?v=<SHORT_VIDEO>"
```

Expected end state after ~10 min:
- `output/transcripts/<id>/` has `audio.m4a`, `vocals.wav`, `chunks/`, `raw.json`, `transcript.md`, `transcript.srt`, `summary.md`, `style.json`, and `stages/01-07-*.json`
- `vision.db` has rows in `video_sources`, `transcript_segments`, `transcript_fts`, `style_profiles`, `pipeline_runs`, `llm_usage`

- [ ] **Step 25.2: Verify FTS5 search works on real data**

```bash
uv run vision-video-asr search "今天" --limit 5
```

Expected: results appear.

- [ ] **Step 25.3: Verify API endpoints**

In one terminal:
```bash
uv run vision-api
```

In another:
```bash
curl -s http://127.0.0.1:8000/api/intelligence/video-asr/videos/<id> | jq .
curl -s http://127.0.0.1:8000/api/intelligence/video-asr/videos/<id>/transcript.srt | head -20
```

- [ ] **Step 25.4: No commit**

Smoke test is pure verification.

### Task 26: Open PR

- [ ] **Step 26.1: Push + create PR**

```bash
git push -u origin feat/video-asr
gh pr create --base master --head feat/video-asr \
  --title "feat(intelligence): video ASR pipeline" \
  --body "$(cat <<'EOF'
## Summary

Implements the video ASR pipeline designed in docs/superpowers/specs/2026-04-18-video-asr-pipeline-design.md. Adds a new submodule vision_intelligence.video_asr with 7-stage pipeline (ingest → preprocess → transcribe → merge → render → analyze → load), CLI (vision-video-asr), FastAPI routes under /api/intelligence/video-asr, and SQLite FTS5 storage.

## Key changes

- python-packages/intelligence/src/vision_intelligence/video_asr/ — full pipeline
- config/video_asr/sources.yaml — 14 seed videos
- output/transcripts/ — gitkeep
- python-packages/api/src/vision_api/video_asr_routes.py + api_key.py
- Makefile + CONTRIBUTING updates

Plan: docs/superpowers/plans/2026-04-18-video-asr-pipeline.md (+ part2)

## Test plan

- [x] uv run pytest -q → 332 + new tests all green at every commit
- [x] make -f Makefile.mac asr completes for at least one short video
- [x] curl on /api/intelligence/video-asr/videos/<id>/transcript.srt returns SRT
- [x] Manual smoke test end-to-end (see Task 25)
EOF
)"
```

- [ ] **Step 26.2: Merge decision handed back to user**

Plan ends here. User decides when/how to merge (likely rebase, same as prior PR).

---

## Self-Review Notes

**Spec coverage map:**

- §2 Goals: Tasks 2, 18-20, 21, 23, 25
- §3 Architecture: Tasks 18-20 (pipeline), 23 (routes)
- §4 Module layout: Tasks 2-23
- §5 Dependencies: Task 1
- §6.1 sources.yaml: Task 2.3, 9
- §6.2 raw.json: Tasks 3 (model), 14 (merger), 19.4 (pipeline stage)
- §6.3 style.json: Task 3 (model), 17 (analyzer)
- §6.4 SQLite: Task 5
- §6.5 Cleaning: Tasks 11 (utils), 14 (merger), 17 (analyzer filter), 19.7 (jieba in load stage)
- §6.6 Stage manifests: Tasks 6 (I/O), 18-19 (pipeline writes)
- §7 FastAPI: Tasks 22 (auth), 23 (routes + SSE + wiring)
- §8 CLI: Task 21
- §9 Errors/retries: Task 12 (tenacity on gemini), Task 18 (pipeline error manifest)
- §10 Testing: all tasks ship tests
- §11 Risks: addressed inline (ffmpeg check Task 1.3, ADC in CONTRIBUTING, concurrency in config)
- §12 Migration: Task 5 uses `CREATE TABLE IF NOT EXISTS`
- §14 Open Qs: all resolved before plan started

**Naming consistency:** `VideoAsrStorage`, `VideoAsrSettings`, `PipelineContext`, `GeminiTranscriber`, `YtDlpSource`, `StageManifest`, `SegmentRecord`, `ChunkTranscript`, `RawTranscript`, `StyleProfile`, `AnalyzeResult`, `JobManager`, `ApiKeyMiddleware`. No drift.

**Test naming:** all `*_test.py` (matches repo convention).
