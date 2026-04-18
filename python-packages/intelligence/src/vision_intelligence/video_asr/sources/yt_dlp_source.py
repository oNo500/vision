"""yt-dlp based source for YouTube + Bilibili."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Literal

from vision_intelligence.video_asr.models import SourceMetadata, SourceName


_YT_ID_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]+?)(?:&|$)")
_BV_RE = re.compile(r"/video/(BV[A-Za-z0-9]+)")


def _run_yt_dlp_json(url: str) -> dict:
    """Shell out to yt-dlp --dump-json. Separated for test mocking."""
    proc = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-warnings", url],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def _run_yt_dlp_download(url: str, output: str) -> int:
    """Shell out to yt-dlp. Returns bytes written. output must be the final file path."""
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
        return _run_yt_dlp_download(url, str(out_path))
