"""Video ASR pipeline configuration via env vars."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_output_root() -> str:
    return str(Path.cwd() / "output" / "transcripts")


class VideoAsrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIDEO_ASR_",
        env_file=".env",
        extra="ignore",
    )

    output_root: str = _default_output_root()
    chunk_duration_sec: int = 500
    chunk_overlap_sec: int = 10
    transcribe_concurrency: int = 3
    gemini_model: str = "gemini-2.5-flash"
    analyze_model: str = "gemini-2.5-flash"
    min_confidence_for_style: float = 0.6
    enable_bgm_removal: bool = True
    gcp_project: str | None = None
    gcp_location: str = "us-central1"
