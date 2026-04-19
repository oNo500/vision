"""FastAPI routes for video ASR (thin shell -> vision_intelligence.video_asr)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api/intelligence/video-asr", tags=["video-asr"])


class JobCreate(BaseModel):
    urls: list[str] | None = None
    sources_yaml: str | None = None


@router.post("/jobs")
async def create_job(body: JobCreate, request: Request) -> dict:
    from vision_intelligence.video_asr.sources.yaml_loader import load_sources
    st = request.app.state.video_asr_storage
    jm = request.app.state.video_asr_jm
    settings = request.app.state.video_asr_settings

    if body.sources_yaml:
        entries = load_sources(body.sources_yaml)
        urls = [e.url for e in entries]
    elif body.urls:
        urls = body.urls
        entries = None
    else:
        raise HTTPException(400, "urls or sources_yaml required")

    job_id = await st.create_or_get_job(urls, source="api")

    async def run_all():
        from vision_intelligence.video_asr.pipeline import (
            PipelineContext, run_video,
        )
        from vision_intelligence.video_asr.sources.registry import get_source
        for u in urls:
            src = get_source(u)
            vid = src.extract_video_id(u)
            await st.link_job_video(job_id, vid)
            video_dir = Path(settings.output_root) / vid
            video_dir.mkdir(parents=True, exist_ok=True)
            ctx = PipelineContext(
                video_id=vid, url=u, video_dir=video_dir,
                storage=st, settings=settings,
            )
            try:
                await run_video(ctx)
            except Exception as exc:
                import structlog
                structlog.get_logger().error("video_pipeline_error", video_id=vid, error=str(exc))
                continue
        await st.set_job_status(job_id, "done")

    jm.submit(job_id, run_all())
    from vision_intelligence.video_asr.sources.registry import get_source
    video_ids = [get_source(u).extract_video_id(u) for u in urls]
    return {"job_id": job_id, "video_ids": video_ids, "status": "accepted"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    st = request.app.state.video_asr_storage
    conn = st._conn
    cur = await conn.execute(
        "SELECT job_id, status FROM asr_jobs WHERE job_id = ?", (job_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "job not found")
    cur = await conn.execute(
        "SELECT video_id FROM asr_job_videos WHERE job_id = ?", (job_id,))
    vids = [r[0] for r in await cur.fetchall()]
    per_video = []
    total_cost = 0.0
    for v in vids:
        cur = await conn.execute(
            "SELECT stage, status, duration_sec FROM pipeline_runs "
            "WHERE video_id = ? ORDER BY started_at", (v,))
        stages = [
            {"stage": r[0], "status": r[1], "duration_sec": r[2]}
            for r in await cur.fetchall()
        ]
        total_cost += await st.sum_cost(v)
        per_video.append({"video_id": v, "stages": stages})
    return {
        "job_id": job_id, "status": row[1],
        "videos": per_video, "cost_usd": round(total_cost, 4),
    }


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> EventSourceResponse:
    st = request.app.state.video_asr_storage
    last_event_id = request.headers.get("last-event-id")

    async def generator():
        try:
            last_seen = int(last_event_id) if last_event_id else 0
        except ValueError:
            last_seen = 0
        while True:
            conn = st._conn
            cur = await conn.execute(
                "SELECT pr.rowid, pr.video_id, pr.stage, pr.status, pr.finished_at "
                "FROM pipeline_runs pr "
                "JOIN asr_job_videos ajv ON pr.video_id = ajv.video_id "
                "WHERE ajv.job_id = ? AND pr.rowid > ? ORDER BY pr.rowid",
                (job_id, last_seen))
            rows = await cur.fetchall()
            for r in rows:
                last_seen = r[0]
                yield {
                    "id": str(last_seen),
                    "event": "stage_update",
                    "data": json.dumps({
                        "video_id": r[1], "stage": r[2], "status": r[3],
                        "finished_at": r[4],
                    }, ensure_ascii=False),
                }
            await asyncio.sleep(1.0)

    return EventSourceResponse(generator())


def _video_dir(settings, video_id: str) -> Path:
    return Path(settings.output_root) / video_id


@router.get("/videos/{video_id}")
async def get_video(video_id: str, request: Request) -> dict:
    st = request.app.state.video_asr_storage
    row = await st.get_video_source(video_id)
    if row is None:
        raise HTTPException(404, "video not found")
    return row


@router.get("/videos/{video_id}/transcript")
async def get_transcript(video_id: str, request: Request) -> dict:
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "raw.json"
    if not p.exists():
        raise HTTPException(404)
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/videos/{video_id}/transcript.md")
async def get_transcript_md(video_id: str, request: Request):
    from fastapi.responses import PlainTextResponse
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "transcript.md"
    if not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/videos/{video_id}/transcript.srt")
async def get_transcript_srt(video_id: str, request: Request):
    from fastapi.responses import PlainTextResponse
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "transcript.srt"
    if not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/plain")


@router.get("/videos/{video_id}/summary")
async def get_summary(video_id: str, request: Request):
    from fastapi.responses import PlainTextResponse
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "summary.md"
    if not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/videos/{video_id}/style")
async def get_style(video_id: str, request: Request) -> dict:
    settings = request.app.state.video_asr_settings
    p = _video_dir(settings, video_id) / "style.json"
    if not p.exists():
        raise HTTPException(404)
    return json.loads(p.read_text(encoding="utf-8"))


class RerunBody(BaseModel):
    stages: list[str] | None = None
    from_stage: str | None = None


@router.post("/videos/{video_id}/rerun")
async def rerun(video_id: str, body: RerunBody, request: Request) -> dict:
    from vision_intelligence.video_asr.pipeline import (
        PipelineContext, run_video,
    )
    st = request.app.state.video_asr_storage
    settings = request.app.state.video_asr_settings
    jm = request.app.state.video_asr_jm

    row = await st.get_video_source(video_id)
    if row is None:
        raise HTTPException(404)
    ctx = PipelineContext(
        video_id=video_id, url=row["url"],
        video_dir=_video_dir(settings, video_id),
        storage=st, settings=settings,
    )

    async def go():
        if body.from_stage:
            await run_video(ctx, from_stage=body.from_stage)
        elif body.stages:
            from vision_intelligence.video_asr.manifest import manifest_path
            for s in body.stages:
                p = manifest_path(ctx.video_dir, s)
                if p.exists():
                    p.unlink()
            await run_video(ctx)
        else:
            await run_video(ctx, from_stage="ingest")

    jm.submit(f"rerun-{video_id}", go())
    return {"video_id": video_id, "status": "restarted"}


@router.get("/search")
async def search(request: Request, q: str, limit: int = 50) -> list[dict]:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    st = request.app.state.video_asr_storage
    return await st.search_segments(jieba_tokenize(q), limit=limit)
