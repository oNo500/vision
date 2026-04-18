# Video ASR Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable video ASR pipeline inside `vision_intelligence.video_asr` that downloads 14 Chinese long videos (YouTube + Bilibili), runs Demucs + Gemini 2.5 Flash to produce transcripts, style profiles, and SQLite FTS5 search, exposed via CLI + FastAPI.

**Architecture:** 7-stage pipeline (ingest → preprocess → transcribe → merge → render → analyze → load). Each stage writes a `stages/NN-<name>.json` manifest and updates a `pipeline_runs` state row. Pluggable source/ASR interfaces via `Protocol`. `pipeline.py` is the orchestrator; `cli.py` and `video_asr_routes.py` are thin shells.

**Tech Stack:** Python 3.13, uv workspace member `vision-intelligence`, `yt-dlp`, `demucs` (PyTorch), `ffmpeg-python`, `google-genai` (Vertex AI, ADC), `litellm`, `typer`, `pydantic` + `pydantic-settings`, `structlog`, `tenacity`, `jieba`, `opencc-python-reimplemented`, FastAPI (existing `vision_api`), SQLite + FTS5 (`aiosqlite`).

**Source spec:** `docs/superpowers/specs/2026-04-18-video-asr-pipeline-design.md`

**Target branch:** `feat/video-asr` (already created in worktree `.worktrees/video-asr/`)

**Baseline:** `uv run pytest -q` → `332 passed` before Task 1; must stay ≥ 332 through the whole plan.

---

## Phase 0 — Scaffolding

### Task 0: Confirm worktree state

- [ ] **Step 0.1: Verify worktree and branch**

```bash
cd /Users/xiu/code/vision/.worktrees/video-asr
git status
git log --oneline -n 1
```

Expected: on `feat/video-asr`, HEAD `6bd3816 docs(specs): add per-stage manifests and from-stage rerun to ASR spec`, tree clean.

- [ ] **Step 0.2: Verify baseline tests green**

```bash
uv run pytest -q 2>&1 | tail -3
```

Expected: `332 passed` (or `332 passed, 1 warning`).

### Task 1: Add `vision-intelligence` runtime dependencies

**Files:**
- Modify: `python-packages/intelligence/pyproject.toml`

- [ ] **Step 1.1: Replace the `dependencies` block**

Current content of `python-packages/intelligence/pyproject.toml`:

```toml
[project]
name = "vision-intelligence"
version = "0.1.0"
description = "Vision intelligence modules (competitor monitoring, topic discovery, content ingestion)"
requires-python = ">=3.13"
license = { text = "MIT" }
dependencies = [
    "vision-shared",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_intelligence"]
```

Replace the whole file with:

```toml
[project]
name = "vision-intelligence"
version = "0.1.0"
description = "Vision intelligence modules (video ASR, competitor monitoring, topic discovery)"
requires-python = ">=3.13"
license = { text = "MIT" }
dependencies = [
    "vision-shared",
    "yt-dlp>=2025.1.0",
    "demucs>=4.0.1",
    "ffmpeg-python>=0.2.0",
    "google-genai>=1.72.0",
    "litellm>=1.50.0",
    "typer>=0.12.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.0",
    "structlog>=24.4.0",
    "tenacity>=9.0.0",
    "jieba>=0.42.1",
    "opencc-python-reimplemented>=0.1.7",
]

[project.scripts]
vision-video-asr = "vision_intelligence.video_asr.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_intelligence"]
```

- [ ] **Step 1.2: Sync**

```bash
uv sync --all-packages 2>&1 | tail -10
```

Expected: uv resolves the new deps (`yt-dlp`, `demucs`, `ffmpeg-python`, `typer`, `structlog`, `tenacity`, `jieba`, `opencc-python-reimplemented`) and their transitives (`torch`, etc.). No errors.

> [!NOTE]
> First sync will download ~2-3 GB (PyTorch for Demucs). Allow ~5 min on first run.

- [ ] **Step 1.3: Verify ffmpeg binary is on PATH**

```bash
which ffmpeg && ffmpeg -version | head -1
```

Expected: prints a path and a version line. If missing: stop and tell the user to `brew install ffmpeg` (macOS).

- [ ] **Step 1.4: Baseline pytest**

```bash
uv run pytest -q 2>&1 | tail -3
```

Expected: `332 passed` (no new tests yet).

- [ ] **Step 1.5: Commit**

```bash
git add python-packages/intelligence/pyproject.toml uv.lock
git commit -m "chore(video-asr): add runtime deps to vision-intelligence"
```

### Task 2: Scaffold `video_asr/` package skeleton

**Files:**
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/__init__.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/sources/__init__.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/asr/__init__.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/prompts/transcribe.md`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/prompts/summarize.md`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/prompts/style.md`
- Create: `config/video_asr/sources.yaml`
- Modify: `.gitignore`
- Create: `output/transcripts/.gitkeep`

- [ ] **Step 2.1: Create empty `__init__.py` files**

```bash
cd /Users/xiu/code/vision/.worktrees/video-asr
mkdir -p python-packages/intelligence/src/vision_intelligence/video_asr/{sources,asr,prompts}
```

Write these three `__init__.py` files (each with just a docstring):

`python-packages/intelligence/src/vision_intelligence/video_asr/__init__.py`:
```python
"""Video ASR pipeline: download → preprocess → transcribe → analyze."""

__version__ = "0.1.0"
```

`python-packages/intelligence/src/vision_intelligence/video_asr/sources/__init__.py`:
```python
"""Video source adapters."""
```

`python-packages/intelligence/src/vision_intelligence/video_asr/asr/__init__.py`:
```python
"""ASR backend adapters."""
```

- [ ] **Step 2.2: Write prompt files (placeholders, content comes in Task 12/17)**

`prompts/transcribe.md`:
```markdown
# Transcribe audio chunk

(content defined in Task 12)
```

`prompts/summarize.md`:
```markdown
# Summarize transcript

(content defined in Task 17)
```

`prompts/style.md`:
```markdown
# Extract style profile

(content defined in Task 17)
```

- [ ] **Step 2.3: Create `config/video_asr/sources.yaml` with the 14 videos**

```bash
mkdir -p config/video_asr
```

Write `config/video_asr/sources.yaml`:

```yaml
videos:
  - id: 0y3O90vyKNo
    source: youtube
    url: https://www.youtube.com/watch?v=0y3O90vyKNo
  - id: sy45qnchmEg
    source: youtube
    url: https://www.youtube.com/watch?v=sy45qnchmEg
  - id: wrHVgPEdN5g
    source: youtube
    url: https://www.youtube.com/watch?v=wrHVgPEdN5g
  - id: IAUFWQPTmAA
    source: youtube
    url: https://www.youtube.com/watch?v=IAUFWQPTmAA
  - id: CZdDu01dGeM
    source: youtube
    url: https://www.youtube.com/watch?v=CZdDu01dGeM
  - id: 6OwSbNsUop4
    source: youtube
    url: https://www.youtube.com/watch?v=6OwSbNsUop4
  - id: 4GQe9btEkqg
    source: youtube
    url: https://www.youtube.com/watch?v=4GQe9btEkqg
  - id: V6K4o0Ns9eQ
    source: youtube
    url: https://www.youtube.com/watch?v=V6K4o0Ns9eQ
  - id: YpSk_c0j3VY
    source: youtube
    url: https://www.youtube.com/watch?v=YpSk_c0j3VY
  - id: SSUKY6MwyN8
    source: youtube
    url: https://www.youtube.com/watch?v=SSUKY6MwyN8
  - id: BV1at4y1h7X4
    source: bilibili
    url: https://www.bilibili.com/video/BV1at4y1h7X4/
  - id: BV1zN4y1H7d7
    source: bilibili
    url: https://www.bilibili.com/video/BV1zN4y1H7d7/
  - id: BV1fN411G7HB
    source: bilibili
    url: https://www.bilibili.com/video/BV1fN411G7HB/
  - id: BV1f64y1V7f2
    source: bilibili
    url: https://www.bilibili.com/video/BV1f64y1V7f2/
```

- [ ] **Step 2.4: Update `.gitignore` — keep `config/video_asr/` tracked**

`config/` is not currently ignored (no `config/*` rule), so `config/video_asr/sources.yaml` will be tracked automatically. Verify:

```bash
git check-ignore -v config/video_asr/sources.yaml 2>&1
echo "---"
git status --short config/
```

Expected: `git check-ignore` prints nothing (exit 1); `git status` shows `?? config/video_asr/sources.yaml`.

- [ ] **Step 2.5: Create `output/transcripts/.gitkeep`**

```bash
mkdir -p output/transcripts
touch output/transcripts/.gitkeep
```

Verify `output/*` is gitignored except `.gitkeep`:

```bash
git check-ignore -v output/transcripts/.gitkeep 2>&1
```

Expected: no output (the `!output/.gitkeep` exception only matches the top-level one). So we also need to widen the exception. Edit `.gitignore` section:

Current:
```
# Output / data (project-specific)
output/*
!output/.gitkeep
data/*
!data/.gitkeep
```

Change to:
```
# Output / data (project-specific)
output/*
!output/.gitkeep
!output/transcripts/
output/transcripts/*
!output/transcripts/.gitkeep
data/*
!data/.gitkeep
```

Re-verify:
```bash
git check-ignore -v output/transcripts/.gitkeep 2>&1
```

Expected: no output (not ignored now).

- [ ] **Step 2.6: Sync + baseline**

```bash
uv sync 2>&1 | tail -3
uv run pytest -q 2>&1 | tail -3
```

Expected: `vision-intelligence` rebuilt with new submodules; `332 passed`.

- [ ] **Step 2.7: Commit**

```bash
git add -A
git commit -m "feat(video-asr): scaffold package + config/sources.yaml + output/transcripts/"
```

---

## Phase 1 — Data Models & Config

### Task 3: Define pydantic models

**Files:**
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/models.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/models_test.py`

- [ ] **Step 3.1: Write failing test**

`python-packages/intelligence/src/vision_intelligence/video_asr/models_test.py`:

```python
"""Tests for video_asr data models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from vision_intelligence.video_asr.models import (
    ChunkTranscript,
    RawTranscript,
    SegmentRecord,
    SourceMetadata,
    StageManifest,
    StyleProfile,
)


def test_source_metadata_roundtrip():
    meta = SourceMetadata(
        video_id="abc",
        source="youtube",
        url="https://www.youtube.com/watch?v=abc",
        title="示例视频",
        uploader="主播 A",
        duration_sec=7234.5,
    )
    assert meta.video_id == "abc"
    again = SourceMetadata.model_validate(meta.model_dump())
    assert again == meta


def test_segment_speaker_enum():
    seg = SegmentRecord(
        idx=0, start=0.0, end=1.5, speaker="host", text="hi",
        text_normalized="hi", confidence=0.9, chunk_id=0,
    )
    assert seg.speaker == "host"
    with pytest.raises(ValidationError):
        SegmentRecord(
            idx=0, start=0.0, end=1.5, speaker="narrator", text="hi",
            text_normalized="hi", confidence=0.9, chunk_id=0,
        )


def test_chunk_transcript_requires_monotonic_times():
    segs = [
        SegmentRecord(idx=0, start=0.0, end=1.0, speaker="host",
                      text="a", text_normalized="a", confidence=0.9, chunk_id=0),
    ]
    ct = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=segs)
    assert ct.chunk_id == 0


def test_raw_transcript_accepts_empty_segments():
    raw = RawTranscript(
        video_id="abc", source="youtube",
        url="https://www.youtube.com/watch?v=abc",
        title="t", uploader="u", duration_sec=1.0,
        asr_model="gemini-2.5-flash", asr_version="2026-04-18",
        processed_at="2026-04-18T00:00:00+08:00",
        bgm_removed=True, segments=[],
    )
    assert raw.segments == []


def test_style_profile_structure():
    style = StyleProfile(
        video_id="abc",
        host_speaking_ratio=0.8,
        speaker_count={"host": 1, "guest": 0, "other": 0, "unknown": 0},
        top_phrases=[{"phrase": "家人们", "count": 10}],
        catchphrases=["冲就完了"],
        opening_hooks=[],
        cta_patterns=[],
        transition_patterns=[],
        sentence_length={"p50": 12.0, "p90": 28.0, "unit": "chars"},
        tone_tags=["热情"],
        english_ratio=0.04,
    )
    assert style.video_id == "abc"


def test_stage_manifest_roundtrip():
    m = StageManifest(
        stage="ingest",
        video_id="abc",
        status="done",
        started_at="2026-04-18T00:00:00+08:00",
        finished_at="2026-04-18T00:01:00+08:00",
        duration_sec=60.0,
        inputs=[],
        outputs=["audio.m4a"],
        tool_versions={"yt-dlp": "2025.1.15"},
        pipeline_version="0.1.0",
    )
    assert m.error is None
    d = m.model_dump()
    again = StageManifest.model_validate(d)
    assert again == m
```

- [ ] **Step 3.2: Run failing test**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/models_test.py -v 2>&1 | tail -10
```

Expected: FAIL `ModuleNotFoundError: No module named 'vision_intelligence.video_asr.models'`.

- [ ] **Step 3.3: Implement models**

`python-packages/intelligence/src/vision_intelligence/video_asr/models.py`:

```python
"""Pydantic models for the video ASR pipeline."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Speaker = Literal["host", "guest", "other", "unknown"]
SourceName = Literal["youtube", "bilibili"]
StageName = Literal[
    "ingest", "preprocess", "transcribe", "merge", "render", "analyze", "load"
]
StageStatus = Literal["pending", "running", "done", "failed"]


class SourceMetadata(BaseModel):
    video_id: str
    source: SourceName
    url: str
    title: str | None = None
    uploader: str | None = None
    duration_sec: float | None = None


class SegmentRecord(BaseModel):
    idx: int
    start: float
    end: float
    speaker: Speaker
    text: str
    text_normalized: str
    confidence: float = Field(ge=0.0, le=1.0)
    chunk_id: int


class ChunkTranscript(BaseModel):
    chunk_id: int
    start_offset: float
    segments: list[SegmentRecord]


class RawTranscript(BaseModel):
    video_id: str
    source: SourceName
    url: str
    title: str | None
    uploader: str | None
    duration_sec: float | None
    asr_model: str
    asr_version: str
    processed_at: str
    bgm_removed: bool
    segments: list[SegmentRecord]


class StyleProfile(BaseModel):
    video_id: str
    host_speaking_ratio: float
    speaker_count: dict[str, int]
    top_phrases: list[dict]
    catchphrases: list[str]
    opening_hooks: list[str]
    cta_patterns: list[str]
    transition_patterns: list[str]
    sentence_length: dict[str, float | str]
    tone_tags: list[str]
    english_ratio: float


class StageManifest(BaseModel):
    stage: StageName
    video_id: str
    status: Literal["done", "failed"]
    started_at: str
    finished_at: str
    duration_sec: float
    inputs: list[str]
    outputs: list[str]
    tool_versions: dict[str, str]
    pipeline_version: str
    error: str | None = None
    # Stage-specific fields live in extra; filled in per-stage helpers.
    extra: dict = Field(default_factory=dict)
```

- [ ] **Step 3.4: Re-run tests**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/models_test.py -v 2>&1 | tail -15
```

Expected: PASS 6/6.

- [ ] **Step 3.5: Full baseline**

```bash
uv run pytest -q 2>&1 | tail -3
```

Expected: `338 passed` (332 + 6 new).

- [ ] **Step 3.6: Commit**

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/models.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/models_test.py
git commit -m "feat(video-asr): add pydantic data models"
```

### Task 4: Config via pydantic-settings

**Files:**
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/config.py`
- Create: `python-packages/intelligence/src/vision_intelligence/video_asr/config_test.py`

- [ ] **Step 4.1: Write failing test**

`python-packages/intelligence/src/vision_intelligence/video_asr/config_test.py`:

```python
"""Tests for video_asr config."""
from __future__ import annotations

from vision_intelligence.video_asr.config import VideoAsrSettings


def test_defaults():
    s = VideoAsrSettings()
    assert s.chunk_duration_sec == 1200  # 20 minutes
    assert s.chunk_overlap_sec == 10
    assert s.transcribe_concurrency == 3
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.output_root.endswith("output/transcripts")
    assert s.min_confidence_for_style == 0.6
    assert s.enable_bgm_removal is True


def test_env_override(monkeypatch):
    monkeypatch.setenv("VIDEO_ASR_CHUNK_DURATION_SEC", "600")
    monkeypatch.setenv("VIDEO_ASR_TRANSCRIBE_CONCURRENCY", "5")
    s = VideoAsrSettings()
    assert s.chunk_duration_sec == 600
    assert s.transcribe_concurrency == 5
```

- [ ] **Step 4.2: Run failing test**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/config_test.py -v 2>&1 | tail -10
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 4.3: Implement**

`python-packages/intelligence/src/vision_intelligence/video_asr/config.py`:

```python
"""Video ASR pipeline configuration via env vars."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_output_root() -> str:
    return str(Path.cwd() / "output" / "transcripts")


class VideoAsrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIDEO_ASR_",
        env_file=".env",
        extra="ignore",
    )

    output_root: str = _default_output_root()
    chunk_duration_sec: int = 1200
    chunk_overlap_sec: int = 10
    transcribe_concurrency: int = 3
    gemini_model: str = "gemini-2.5-flash"
    analyze_model: str = "gemini-2.5-flash"
    min_confidence_for_style: float = 0.6
    enable_bgm_removal: bool = True
    gcp_project: str | None = None
    gcp_location: str = "us-central1"
```

- [ ] **Step 4.4: Run tests**

```bash
uv run pytest python-packages/intelligence/src/vision_intelligence/video_asr/config_test.py -v 2>&1 | tail -10
```

Expected: PASS 2/2.

- [ ] **Step 4.5: Commit**

```bash
git add python-packages/intelligence/src/vision_intelligence/video_asr/config.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/config_test.py
git commit -m "feat(video-asr): add settings with env override"
```

---

## Phase 2 — Storage Layer

Continued in [Part 2](2026-04-18-video-asr-pipeline-part2.md).

The remaining phases:
- Phase 2: Storage (Task 5-6) — SQLite schema, CRUD, FTS5, stage manifest I/O
- Phase 3: Sources (Task 7-9) — yt-dlp wrapper + registry
- Phase 4: Preprocessor (Task 10-11) — Demucs + ffmpeg chunking
- Phase 5: ASR (Task 12-13) — Gemini transcribe + prompt
- Phase 6: Merger (Task 14) — dedupe + cleaning
- Phase 7: Renderer (Task 15) — md + srt output
- Phase 8: Analyzer (Task 16-17) — summary + style profile
- Phase 9: Pipeline + Jobs (Task 18-20) — orchestration + job manager + stage manifests
- Phase 10: CLI (Task 21) — typer commands
- Phase 11: FastAPI routes (Task 22-23) — HTTP endpoints + SSE + auth
- Phase 12: Integration (Task 24-26) — first real-video smoke run, Makefile target, PR

**Total:** ~26 tasks, ~120 TDD steps.

> [!IMPORTANT]
> This plan is split across two files to stay within file-size limits. Part 2 contains the executable TDD steps for Tasks 5-26. Read both before execution.
