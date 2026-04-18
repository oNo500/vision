"""URL -> VideoSource router."""
from __future__ import annotations

from vision_intelligence.video_asr.sources.base import VideoSource
from vision_intelligence.video_asr.sources.yt_dlp_source import YtDlpSource


def get_source(url: str) -> VideoSource:
    if any(h in url for h in ("youtube.com", "youtu.be", "bilibili.com")):
        return YtDlpSource()
    raise ValueError(f"No source registered for URL: {url}")
