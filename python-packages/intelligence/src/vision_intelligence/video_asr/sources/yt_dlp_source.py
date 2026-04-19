"""yt-dlp based source for YouTube + Bilibili."""
from __future__ import annotations

import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path

import yt_dlp

from vision_intelligence.video_asr.models import SourceMetadata, SourceName


_YT_ID_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]+?)(?:&|$)")
_BV_RE = re.compile(r"/video/(BV[A-Za-z0-9]+)")

# Callback type: (downloaded_bytes, total_bytes | None) -> None
ProgressCallback = Callable[[int, int | None], None]

_PROGRESS_INTERVAL = 0.1  # seconds between progress updates


def _ffmpeg_dir() -> str | None:
    p = shutil.which("ffmpeg")
    return str(Path(p).parent) if p else None


def _run_yt_dlp_json(url: str) -> dict:
    """Fetch video metadata via yt-dlp Python API."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        return ydl.extract_info(url, download=False)


def _run_yt_dlp_download(
    url: str, output: Path, progress_cb: ProgressCallback | None = None
) -> int:
    """Download audio via yt-dlp Python API. Returns bytes written.

    `output` must be the final .m4a path; yt-dlp outtmpl is set to the stem
    so FFmpegExtractAudio writes exactly <stem>.m4a without double-extension.
    """
    last_update = 0.0

    def _hook(d: dict) -> None:
        nonlocal last_update
        if progress_cb is None:
            return
        if d["status"] == "downloading":
            now = time.monotonic()
            if now - last_update < _PROGRESS_INTERVAL:
                return
            last_update = now
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            progress_cb(downloaded, total)
        elif d["status"] == "finished":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            progress_cb(total or 0, total)

    # Strip extension so yt-dlp uses the stem as outtmpl; FFmpegExtractAudio
    # then appends .m4a, producing exactly `output` (e.g. audio.m4a).
    stem = str(output.with_suffix(""))
    opts = {
        "format": "bestaudio/best",
        "outtmpl": stem,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "0",
        }],
        "continuedl": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
    }
    ffmpeg = _ffmpeg_dir()
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return output.stat().st_size


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

    def download_audio(
        self, url: str, out_path: Path,
        progress_cb: ProgressCallback | None = None,
    ) -> int:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return _run_yt_dlp_download(url, out_path, progress_cb)
