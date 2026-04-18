"""VideoSource interface."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vision_intelligence.video_asr.models import SourceMetadata


class VideoSource(Protocol):
    name: str

    def fetch_metadata(self, url: str) -> SourceMetadata: ...

    def download_audio(self, url: str, out_path: Path) -> int:
        """Download audio to out_path. Return bytes written."""
