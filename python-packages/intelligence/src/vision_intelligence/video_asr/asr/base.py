"""Transcriber protocol."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vision_intelligence.video_asr.models import ChunkTranscript


class Transcriber(Protocol):
    name: str

    def transcribe_chunk(
        self, audio_path: Path, *, chunk_id: int, start_offset: float,
    ) -> ChunkTranscript: ...
