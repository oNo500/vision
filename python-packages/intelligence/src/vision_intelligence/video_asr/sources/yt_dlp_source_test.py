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
