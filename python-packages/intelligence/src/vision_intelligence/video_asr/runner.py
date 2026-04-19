"""CLI command implementations — thin wrappers over pipeline/storage."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from vision_intelligence.video_asr.config import VideoAsrSettings
from vision_intelligence.video_asr.pipeline import PipelineContext, run_video
from vision_intelligence.video_asr.sources.registry import get_source
from vision_intelligence.video_asr.sources.yaml_loader import load_sources
from vision_intelligence.video_asr.storage import VideoAsrStorage


async def _open_storage(settings: VideoAsrSettings) -> tuple[aiosqlite.Connection, VideoAsrStorage]:
    db_path = Path("vision.db")
    conn = await aiosqlite.connect(db_path)
    st = VideoAsrStorage(conn)
    await st.init_schema()
    return conn, st


async def run_cli_job(*, sources_yaml: Path | None, url: str | None) -> None:
    if not sources_yaml and not url:
        sys.stderr.write("Must provide --sources or --url\n"); sys.exit(2)
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        if sources_yaml:
            entries = load_sources(str(sources_yaml))
            urls = [e.url for e in entries]
            job_id = await st.create_or_get_job(urls, source="cli")
            print(f"job_id={job_id}")
            for e in entries:
                await _run_one(st, settings, e.url, e.video_id, job_id)
            await st.set_job_status(job_id, "done")
        else:
            src = get_source(url)
            video_id = src.extract_video_id(url)
            job_id = await st.create_or_get_job([url], source="cli")
            print(f"job_id={job_id}")
            await _run_one(st, settings, url, video_id, job_id)
            await st.set_job_status(job_id, "done")
    finally:
        await conn.close()


async def _run_one(
    st: VideoAsrStorage, settings: VideoAsrSettings,
    url: str, video_id: str, job_id: str,
) -> None:
    await st.link_job_video(job_id, video_id)
    video_dir = Path(settings.output_root) / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    ctx = PipelineContext(
        video_id=video_id, url=url, video_dir=video_dir,
        storage=st, settings=settings,
    )
    try:
        await run_video(ctx)
    except Exception as e:
        print(f"[{video_id}] FAILED: {e!r}")


async def show_status(job_id: str) -> None:
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        cur = await conn.execute(
            "SELECT video_id FROM asr_job_videos WHERE job_id = ?", (job_id,))
        rows = await cur.fetchall()
        for r in rows:
            vid = r[0]
            print(f"--- {vid} ---")
            cur2 = await conn.execute(
                "SELECT stage, status, duration_sec FROM pipeline_runs "
                "WHERE video_id = ? ORDER BY started_at", (vid,))
            for stage, status, dur in await cur2.fetchall():
                print(f"  {stage}: {status}  ({dur}s)")
    finally:
        await conn.close()


async def rerun_video(
    video_id: str, *, stages: str | None, from_stage: str | None,
) -> None:
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        video_dir = Path(settings.output_root) / video_id
        cur = await conn.execute(
            "SELECT url FROM video_sources WHERE video_id = ?", (video_id,))
        row = await cur.fetchone()
        if row is None:
            print(f"unknown video_id {video_id}"); sys.exit(1)
        url = row[0]
        ctx = PipelineContext(
            video_id=video_id, url=url, video_dir=video_dir,
            storage=st, settings=settings,
        )
        if from_stage:
            await run_video(ctx, from_stage=from_stage)
        elif stages:
            from vision_intelligence.video_asr.manifest import manifest_path
            for s in stages.split(","):
                p = manifest_path(video_dir, s.strip())
                if p.exists():
                    p.unlink()
            await run_video(ctx)
        else:
            await run_video(ctx, from_stage="ingest")
    finally:
        await conn.close()


async def search_fts(q: str, *, limit: int) -> None:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        query = jieba_tokenize(q)
        hits = await st.search_segments(query, limit=limit)
        for h in hits:
            print(f"[{h['video_id']}] t={h['start']:.1f}s ({h['speaker']}): {h['text']}")
    finally:
        await conn.close()


async def download_sources(
    *, sources_yaml: Path | None, url: str | None, concurrency: int = 3,
) -> None:
    """Download audio for all sources (ingest stage only), concurrently."""
    if not sources_yaml and not url:
        sys.stderr.write("Must provide --sources or --url\n")
        sys.exit(2)
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        if sources_yaml:
            entries = load_sources(str(sources_yaml))
        else:
            from vision_intelligence.video_asr.sources.yaml_loader import SourceEntry
            src = get_source(url)
            video_id = src.extract_video_id(url)
            entries = [SourceEntry(video_id=video_id, url=url, source=src.name)]

        sem = asyncio.Semaphore(concurrency)

        async def _download_one(entry) -> None:
            async with sem:
                video_dir = Path(settings.output_root) / entry.video_id
                video_dir.mkdir(parents=True, exist_ok=True)
                ctx = PipelineContext(
                    video_id=entry.video_id, url=entry.url,
                    video_dir=video_dir, storage=st, settings=settings,
                )
                # run_video skips stages with existing DONE manifests;
                # stop after ingest by raising StopIteration via a wrapper
                from vision_intelligence.video_asr.manifest import read_manifest
                if read_manifest(video_dir, "ingest") and \
                        read_manifest(video_dir, "ingest").status == "done":
                    print(f"[{entry.video_id}] ingest already done, skipping")
                    return
                try:
                    await _run_ingest(ctx)
                    print(f"[{entry.video_id}] downloaded")
                except Exception as exc:
                    import structlog
                    structlog.get_logger().error(
                        "download_error", video_id=entry.video_id, error=str(exc))
                    print(f"[{entry.video_id}] FAILED: {exc!r}")

        await asyncio.gather(*[_download_one(e) for e in entries])
    finally:
        await conn.close()


async def _run_ingest(ctx: PipelineContext) -> None:
    """Run only the ingest stage, writing manifest and storage row."""
    from datetime import datetime, timezone

    from vision_intelligence.video_asr.manifest import write_manifest
    from vision_intelligence.video_asr.models import StageManifest
    from vision_intelligence.video_asr.pipeline import _stage_ingest

    def _now() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat()

    def _delta_sec(a: str, b: str) -> float:
        from datetime import datetime
        fmt = datetime.fromisoformat
        return (fmt(b) - fmt(a)).total_seconds()

    await ctx.storage.set_pipeline_run(
        video_id=ctx.video_id, stage="ingest",
        status="running", started_at=_now(),
    )
    started = _now()
    try:
        extra = await _stage_ingest(ctx) or {}
        finished = _now()
        m = StageManifest(
            stage="ingest", video_id=ctx.video_id, status="done",
            started_at=started, finished_at=finished,
            duration_sec=_delta_sec(started, finished),
            inputs=extra.pop("inputs", []),
            outputs=extra.pop("outputs", []),
            tool_versions=extra.pop("tool_versions", {}),
            pipeline_version=ctx.pipeline_version,
            extra=extra,
        )
        write_manifest(ctx.video_dir, m)
        await ctx.storage.set_pipeline_run(
            video_id=ctx.video_id, stage="ingest", status="done",
            started_at=started, finished_at=finished,
            duration_sec=m.duration_sec,
        )
    except Exception as e:
        finished = _now()
        m = StageManifest(
            stage="ingest", video_id=ctx.video_id, status="failed",
            started_at=started, finished_at=finished,
            duration_sec=_delta_sec(started, finished),
            inputs=[], outputs=[], tool_versions={},
            pipeline_version=ctx.pipeline_version,
            error=repr(e),
        )
        write_manifest(ctx.video_dir, m)
        await ctx.storage.set_pipeline_run(
            video_id=ctx.video_id, stage="ingest", status="failed",
            started_at=started, finished_at=finished,
            duration_sec=m.duration_sec, error=repr(e),
        )
        raise


async def export_all(format: str) -> None:
    settings = VideoAsrSettings()
    conn, st = await _open_storage(settings)
    try:
        cur = await conn.execute(
            "SELECT video_id, idx, start, end, speaker, text FROM transcript_segments "
            "ORDER BY video_id, idx")
        if format == "jsonl":
            async for row in cur:
                sys.stdout.write(json.dumps({
                    "video_id": row[0], "idx": row[1], "start": row[2],
                    "end": row[3], "speaker": row[4], "text": row[5],
                }, ensure_ascii=False) + "\n")
    finally:
        await conn.close()
