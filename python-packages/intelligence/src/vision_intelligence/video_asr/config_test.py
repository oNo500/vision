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
