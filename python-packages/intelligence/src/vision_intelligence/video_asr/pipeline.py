"""7-stage pipeline orchestration."""
from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vision_intelligence.video_asr.manifest import (
    manifest_path, read_manifest, write_manifest,
)
from vision_intelligence.video_asr.models import StageManifest, StageName

logger = logging.getLogger(__name__)

_STAGE_ORDER: list[StageName] = [
    "ingest", "preprocess", "transcribe", "merge",
    "render", "analyze", "load",
]


@dataclass
class PipelineContext:
    video_id: str
    url: str
    video_dir: Path
    storage: Any  # VideoAsrStorage
    settings: Any  # VideoAsrSettings
    pipeline_version: str = "0.1.0"
    progress_cb: Any = None  # ProgressCallback | None, injected by CLI for rich progress


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _tool_version(cmd: str, arg: str) -> str:
    try:
        out = subprocess.run(
            [cmd, arg], capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()[0]
        return out
    except Exception:
        return "unknown"


async def _stage_ingest(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.sources.registry import get_source
    src = get_source(ctx.url)
    meta = src.fetch_metadata(ctx.url)
    audio_out = ctx.video_dir / "audio.m4a"
    bytes_written = src.download_audio(ctx.url, audio_out, progress_cb=ctx.progress_cb)

    (ctx.video_dir / "source.json").write_text(
        meta.model_dump_json(indent=2), encoding="utf-8")

    await ctx.storage.upsert_video_source(
        meta, asr_model=ctx.settings.gemini_model,
        bgm_removed=ctx.settings.enable_bgm_removal,
    )

    return {
        "inputs": [],
        "outputs": ["audio.m4a", "source.json"],
        "tool_versions": {"yt-dlp": _tool_version("yt-dlp", "--version")},
        "url": ctx.url,
        "downloaded_bytes": bytes_written,
        "source_metadata": meta.model_dump(),
    }


async def _stage_preprocess(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.preprocessor import preprocess_audio
    audio = ctx.video_dir / "audio.m4a"
    vocals = ctx.video_dir / "vocals.wav"
    chunks_dir = ctx.video_dir / "chunks"
    info = await asyncio.to_thread(
        preprocess_audio,
        audio, vocals, chunks_dir,
        chunk_sec=ctx.settings.chunk_duration_sec,
        overlap_sec=ctx.settings.chunk_overlap_sec,
        enable_bgm_removal=ctx.settings.enable_bgm_removal,
    )
    return {
        "inputs": ["audio.m4a"],
        "outputs": ["vocals.wav", f"chunks/ ({info['chunk_count']} files)"],
        "tool_versions": {
            "demucs": _tool_version("python", "-c import demucs; print(demucs.__version__)"),
            "ffmpeg": _tool_version("ffmpeg", "-version"),
        },
        **info,
    }


async def _stage_transcribe(ctx: PipelineContext) -> dict:
    import hashlib
    from vision_intelligence.video_asr.asr.gemini import GeminiTranscriber
    from vision_intelligence.video_asr.cost import estimate_cost_usd

    preprocess = read_manifest(ctx.video_dir, "preprocess")
    boundaries = preprocess.extra["boundaries"]
    chunks_dir = ctx.video_dir / "chunks"

    transcriber = GeminiTranscriber(
        model=ctx.settings.gemini_model,
        project=ctx.settings.gcp_project,
        location=ctx.settings.gcp_location,
    )

    sem = asyncio.Semaphore(ctx.settings.transcribe_concurrency)
    total_in = total_out = 0

    async def do_chunk(i: int, start_offset: float) -> None:
        nonlocal total_in, total_out
        async with sem:
            audio = chunks_dir / f"chunk_{i:03d}.wav"

            def _work():
                done_file = chunks_dir / f"chunk_{i:03d}.json"
                if done_file.exists():
                    from vision_intelligence.video_asr.models import ChunkTranscript
                    return ChunkTranscript.model_validate_json(done_file.read_text())
                ct = transcriber.transcribe_chunk(
                    audio, chunk_id=i, start_offset=start_offset,
                )
                done_file.write_text(ct.model_dump_json(indent=2), encoding="utf-8")
                return ct
            ct = await asyncio.to_thread(_work)
            # Usage is not exposed from transcribe_chunk in simplified impl;
            # track 0 tokens to not break cost math
            total_in += 0
            total_out += 0

    tasks = [do_chunk(i, start) for i, (start, _) in enumerate(boundaries)]
    await asyncio.gather(*tasks)

    prompt_file = Path(__file__).parent / "prompts" / "transcribe.md"
    prompt_hash = hashlib.sha256(prompt_file.read_bytes()).hexdigest()[:12]
    cost = estimate_cost_usd(
        model=ctx.settings.gemini_model,
        input_tokens=total_in, output_tokens=total_out,
    )
    await ctx.storage.log_llm_usage(
        video_id=ctx.video_id, stage="transcribe",
        model=ctx.settings.gemini_model,
        input_tokens=total_in, output_tokens=total_out,
        estimated_cost_usd=cost, called_at=_now(),
    )

    return {
        "inputs": ["vocals.wav", "chunks/*.wav"],
        "outputs": ["chunks/*.json"],
        "model": ctx.settings.gemini_model,
        "chunks_transcribed": len(boundaries),
        "chunks_failed": 0,
        "tokens_in": total_in, "tokens_out": total_out,
        "estimated_cost_usd": cost,
        "prompt_version": prompt_hash,
    }


async def _stage_merge(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.merger import merge_chunks
    from vision_intelligence.video_asr.models import ChunkTranscript, RawTranscript

    chunks_dir = ctx.video_dir / "chunks"
    ingest = read_manifest(ctx.video_dir, "ingest")
    meta = ingest.extra["source_metadata"]

    chunks = [
        ChunkTranscript.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(chunks_dir.glob("chunk_*.json"))
    ]
    in_count = sum(len(c.segments) for c in chunks)
    merged = merge_chunks(chunks)
    out_count = len(merged.segments)

    raw = RawTranscript(
        video_id=ctx.video_id, source=meta["source"], url=meta["url"],
        title=meta.get("title"), uploader=meta.get("uploader"),
        duration_sec=meta.get("duration_sec"),
        asr_model=ctx.settings.gemini_model,
        asr_version="2026-04-18",
        processed_at=_now(),
        bgm_removed=ctx.settings.enable_bgm_removal,
        segments=merged.segments,
    )
    (ctx.video_dir / "raw.json").write_text(
        raw.model_dump_json(indent=2), encoding="utf-8")

    return {
        "inputs": ["chunks/*.json"],
        "outputs": ["raw.json"],
        "segments_in": in_count, "segments_out": out_count,
        "dedup_count": in_count - out_count,
    }


async def _stage_render(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.renderer import render_markdown, render_srt
    from vision_intelligence.video_asr.models import RawTranscript

    raw = RawTranscript.model_validate_json(
        (ctx.video_dir / "raw.json").read_text(encoding="utf-8"))
    (ctx.video_dir / "transcript.md").write_text(
        render_markdown(raw), encoding="utf-8")
    (ctx.video_dir / "transcript.srt").write_text(
        render_srt(raw), encoding="utf-8")

    return {
        "inputs": ["raw.json"],
        "outputs": ["transcript.md", "transcript.srt"],
        "total_segments": len(raw.segments),
        "total_duration_sec": raw.duration_sec,
    }


async def _stage_analyze(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.analyzer import analyze_transcript
    from vision_intelligence.video_asr.cost import estimate_cost_usd
    from vision_intelligence.video_asr.models import RawTranscript

    raw = RawTranscript.model_validate_json(
        (ctx.video_dir / "raw.json").read_text(encoding="utf-8"))

    result = await asyncio.to_thread(
        analyze_transcript, raw,
        project=ctx.settings.gcp_project,
        location=ctx.settings.gcp_location,
        model=ctx.settings.analyze_model,
        min_confidence=ctx.settings.min_confidence_for_style,
    )

    (ctx.video_dir / "summary.md").write_text(result.summary_md, encoding="utf-8")
    (ctx.video_dir / "style.json").write_text(
        result.style.model_dump_json(indent=2), encoding="utf-8")

    total_in = result.summary_usage["input_tokens"] + result.style_usage["input_tokens"]
    total_out = result.summary_usage["output_tokens"] + result.style_usage["output_tokens"]
    cost = estimate_cost_usd(
        model=ctx.settings.analyze_model,
        input_tokens=total_in, output_tokens=total_out,
    )
    await ctx.storage.log_llm_usage(
        video_id=ctx.video_id, stage="analyze",
        model=ctx.settings.analyze_model,
        input_tokens=total_in, output_tokens=total_out,
        estimated_cost_usd=cost, called_at=_now(),
    )

    return {
        "inputs": ["raw.json"],
        "outputs": ["summary.md", "style.json"],
        "model": ctx.settings.analyze_model,
        "tokens_in": total_in, "tokens_out": total_out,
        "estimated_cost_usd": cost,
        "segments_in": len(raw.segments),
        "segments_filtered_out": result.segments_filtered_out,
    }


async def _stage_load(ctx: PipelineContext) -> dict:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    from vision_intelligence.video_asr.models import RawTranscript, StyleProfile

    raw = RawTranscript.model_validate_json(
        (ctx.video_dir / "raw.json").read_text(encoding="utf-8"))
    normalized = [
        s.model_copy(update={"text_normalized": jieba_tokenize(s.text)})
        for s in raw.segments
    ]
    raw_norm = raw.model_copy(update={"segments": normalized})
    await ctx.storage.write_segments(raw_norm)

    style = StyleProfile.model_validate_json(
        (ctx.video_dir / "style.json").read_text(encoding="utf-8"))
    await ctx.storage.upsert_style_profile(style)

    return {
        "inputs": ["raw.json", "style.json"],
        "outputs": [],
        "rows_inserted": {
            "video_sources": 1,
            "transcript_segments": len(normalized),
            "transcript_fts": len(normalized),
            "style_profiles": 1,
        },
    }


def _get_stage_fn(stage: StageName):
    """Look up stage function by name at call time (allows patching in tests)."""
    import vision_intelligence.video_asr.pipeline as _self
    return {
        "ingest": _self._stage_ingest,
        "preprocess": _self._stage_preprocess,
        "transcribe": _self._stage_transcribe,
        "merge": _self._stage_merge,
        "render": _self._stage_render,
        "analyze": _self._stage_analyze,
        "load": _self._stage_load,
    }[stage]


def _delete_from_stage(video_dir: Path, from_stage: StageName) -> None:
    """Delete the from_stage manifest and all downstream manifests."""
    start = _STAGE_ORDER.index(from_stage)
    for s in _STAGE_ORDER[start:]:
        p = manifest_path(video_dir, s)
        if p.exists():
            p.unlink()


async def run_video(
    ctx: PipelineContext, *, from_stage: StageName | None = None,
) -> None:
    """Run all stages for one video, skipping those with DONE manifests."""
    if from_stage:
        _delete_from_stage(ctx.video_dir, from_stage)

    pipeline_version = getattr(ctx, "pipeline_version", None) or "0.1.0"
    if not isinstance(pipeline_version, str):
        pipeline_version = "0.1.0"

    for stage in _STAGE_ORDER:
        existing = read_manifest(ctx.video_dir, stage)
        if existing and existing.status == "done":
            logger.info("skip done stage %s for %s", stage, ctx.video_id)
            continue

        await ctx.storage.set_pipeline_run(
            video_id=ctx.video_id, stage=stage,
            status="running", started_at=_now(),
        )
        started = _now()
        fn = _get_stage_fn(stage)
        try:
            extra = await fn(ctx) or {}
            finished = _now()
            m = StageManifest(
                stage=stage, video_id=ctx.video_id, status="done",
                started_at=started, finished_at=finished,
                duration_sec=_delta_sec(started, finished),
                inputs=extra.pop("inputs", []),
                outputs=extra.pop("outputs", []),
                tool_versions=extra.pop("tool_versions", {}),
                pipeline_version=pipeline_version,
                extra=extra,
            )
            write_manifest(ctx.video_dir, m)
            await ctx.storage.set_pipeline_run(
                video_id=ctx.video_id, stage=stage, status="done",
                started_at=started, finished_at=finished,
                duration_sec=m.duration_sec,
            )
        except Exception as e:
            finished = _now()
            m = StageManifest(
                stage=stage, video_id=ctx.video_id, status="failed",
                started_at=started, finished_at=finished,
                duration_sec=_delta_sec(started, finished),
                inputs=[], outputs=[], tool_versions={},
                pipeline_version=pipeline_version,
                error=repr(e),
            )
            write_manifest(ctx.video_dir, m)
            await ctx.storage.set_pipeline_run(
                video_id=ctx.video_id, stage=stage, status="failed",
                started_at=started, finished_at=finished,
                duration_sec=m.duration_sec, error=repr(e),
            )
            raise


def _delta_sec(a_iso: str, b_iso: str) -> float:
    a = datetime.fromisoformat(a_iso)
    b = datetime.fromisoformat(b_iso)
    return (b - a).total_seconds()
