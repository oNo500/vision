"""Merge chunk transcripts -> monotonic raw.json with cleaning (§6.5.1)."""
from __future__ import annotations

import difflib
import logging

from vision_intelligence.video_asr.cleaning import (
    normalize_punctuation, traditional_to_simplified,
)
from vision_intelligence.video_asr.models import ChunkTranscript, SegmentRecord

logger = logging.getLogger(__name__)


_PUNCT_STRIP = str.maketrans("", "", "，。？！；：,.?!;:")


def _is_near_duplicate(a: str, b: str) -> bool:
    a_norm = a.translate(_PUNCT_STRIP)
    b_norm = b.translate(_PUNCT_STRIP)
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio() >= 0.9


def _sanitize_timestamps(segs: list[SegmentRecord]) -> list[SegmentRecord]:
    out: list[SegmentRecord] = []
    for s in segs:
        if not s.text.strip():
            continue
        if s.start > s.end:
            logger.warning("swapping start/end for seg idx=%s", s.idx)
            s = s.model_copy(update={"start": s.end, "end": s.start})
        out.append(s)
    return out


def _clean_text(s: str) -> str:
    return normalize_punctuation(traditional_to_simplified(s))


class MergedTranscript:
    """Simple container; real SegmentRecord list output."""
    def __init__(self, segments: list[SegmentRecord]) -> None:
        self.segments = segments


def merge_chunks(chunks: list[ChunkTranscript]) -> MergedTranscript:
    # Collect + clean
    all_segs: list[SegmentRecord] = []
    for c in chunks:
        for s in c.segments:
            cleaned = _clean_text(s.text)
            all_segs.append(s.model_copy(update={"text": cleaned}))
    all_segs = _sanitize_timestamps(all_segs)

    # Sort by start; dedupe near-duplicates whose times overlap
    all_segs.sort(key=lambda s: (s.start, s.end))
    merged: list[SegmentRecord] = []
    for s in all_segs:
        if merged:
            prev = merged[-1]
            # Overlap window (last 15s) + near-text match -> skip
            if s.start <= prev.end + 5.0 and _is_near_duplicate(s.text, prev.text):
                continue
        merged.append(s)

    # Renumber idx sequentially
    renumbered = [
        s.model_copy(update={"idx": i}) for i, s in enumerate(merged)
    ]
    return MergedTranscript(segments=renumbered)
