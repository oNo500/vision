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
    asr_engine: str = "gemini"


class ChunkTranscript(BaseModel):
    chunk_id: int
    start_offset: float
    segments: list[SegmentRecord]
    asr_engine: str = "gemini"


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
    extra: dict = Field(default_factory=dict)
