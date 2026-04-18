"""Stage manifest file I/O (output/transcripts/<vid>/stages/NN-<name>.json)."""
from __future__ import annotations

from pathlib import Path

from vision_intelligence.video_asr.models import StageManifest, StageName

_STAGE_ORDER: dict[StageName, int] = {
    "ingest": 1, "preprocess": 2, "transcribe": 3, "merge": 4,
    "render": 5, "analyze": 6, "load": 7,
}


def manifest_path(video_dir: Path, stage: StageName) -> Path:
    n = _STAGE_ORDER[stage]
    return video_dir / "stages" / f"{n:02d}-{stage}.json"


def write_manifest(video_dir: Path, m: StageManifest) -> None:
    p = manifest_path(video_dir, m.stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(m.model_dump_json(indent=2), encoding="utf-8")


def read_manifest(video_dir: Path, stage: StageName) -> StageManifest | None:
    p = manifest_path(video_dir, stage)
    if not p.exists():
        return None
    return StageManifest.model_validate_json(p.read_text(encoding="utf-8"))
