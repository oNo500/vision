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
