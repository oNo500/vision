"""Parse config/video_asr/sources.yaml -> list[SourceEntry]."""
from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass
class SourceEntry:
    video_id: str
    source: str
    url: str


def load_sources(yaml_path: str) -> list[SourceEntry]:
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [
        SourceEntry(
            video_id=v["id"],
            source=v["source"],
            url=v["url"],
        )
        for v in data["videos"]
    ]
