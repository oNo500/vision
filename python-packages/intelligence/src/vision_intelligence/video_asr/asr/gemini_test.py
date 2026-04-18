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
    # Relative 0.0 -> absolute 1190.0
    assert ct.segments[0].start == 1190.0
    assert ct.segments[0].end == 1192.0
