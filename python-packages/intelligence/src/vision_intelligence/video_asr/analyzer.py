"""Analyzer: summary + style profile via Gemini."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from vision_intelligence.video_asr.models import (
    RawTranscript, SegmentRecord, StyleProfile,
)


@dataclass
class AnalyzeResult:
    summary_md: str
    style: StyleProfile
    summary_usage: dict
    style_usage: dict
    segments_filtered_out: int


def _filter_for_style(
    segs: list[SegmentRecord], *, min_conf: float,
) -> list[SegmentRecord]:
    return [s for s in segs if s.speaker == "host" and s.confidence >= min_conf]


def _load(name: str) -> str:
    return (Path(__file__).parent / "prompts" / name).read_text(encoding="utf-8")


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=2, min=10, max=120), reraise=True)
def _call_summary(*, client, model: str, transcript_text: str) -> tuple[str, dict]:
    resp = client.models.generate_content(
        model=model,
        contents=[_load("summarize.md"), transcript_text],
    )
    usage = {
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) or 0,
    }
    return resp.text, usage


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=2, min=10, max=120), reraise=True)
def _call_style(*, client, model: str, host_text: str) -> tuple[dict, dict]:
    from google.genai import types as gtypes
    resp = client.models.generate_content(
        model=model,
        contents=[_load("style.md"), host_text],
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    import json
    data = json.loads(resp.text)
    usage = {
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) or 0,
    }
    return data, usage


def _sentence_length_stats(segs: list[SegmentRecord]) -> dict:
    lens = sorted(len(s.text) for s in segs) or [0]

    def pct(p: float) -> float:
        i = max(0, int(round(p * (len(lens) - 1))))
        return float(lens[i])

    return {"p50": pct(0.5), "p90": pct(0.9), "unit": "chars"}


def _speaker_count(segs: list[SegmentRecord]) -> dict[str, int]:
    c = Counter(s.speaker for s in segs)
    return {k: int(c.get(k, 0)) for k in ("host", "guest", "other", "unknown")}


def analyze_transcript(
    raw: RawTranscript, *,
    project: str, location: str, model: str, min_confidence: float,
) -> AnalyzeResult:
    from google import genai
    client = genai.Client(vertexai=True, project=project, location=location)

    full_text = "\n".join(f"[{s.speaker}] {s.text}" for s in raw.segments)
    summary_md, summary_usage = _call_summary(
        client=client, model=model, transcript_text=full_text,
    )

    host_segs = _filter_for_style(raw.segments, min_conf=min_confidence)
    host_text = "\n".join(s.text for s in host_segs)
    style_dict, style_usage = _call_style(
        client=client, model=model, host_text=host_text,
    )

    total_chars = sum(len(s.text) for s in raw.segments) or 1
    host_chars = sum(len(s.text) for s in raw.segments if s.speaker == "host")
    english_chars = sum(
        1 for s in raw.segments for c in s.text
        if "a" <= c.lower() <= "z"
    )
    sp_counts = _speaker_count(raw.segments)

    style = StyleProfile(
        video_id=raw.video_id,
        host_speaking_ratio=host_chars / total_chars if total_chars else 0.0,
        speaker_count=sp_counts,
        top_phrases=style_dict.get("top_phrases", []),
        catchphrases=style_dict.get("catchphrases", []),
        opening_hooks=style_dict.get("opening_hooks", []),
        cta_patterns=style_dict.get("cta_patterns", []),
        transition_patterns=style_dict.get("transition_patterns", []),
        sentence_length=_sentence_length_stats(raw.segments),
        tone_tags=style_dict.get("tone_tags", []),
        english_ratio=english_chars / total_chars if total_chars else 0.0,
    )

    return AnalyzeResult(
        summary_md=summary_md,
        style=style,
        summary_usage=summary_usage,
        style_usage=style_usage,
        segments_filtered_out=len(raw.segments) - len(host_segs),
    )
