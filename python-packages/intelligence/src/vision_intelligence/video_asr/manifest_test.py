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
