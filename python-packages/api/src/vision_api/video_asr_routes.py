"""FastAPI routes for video ASR (thin shell -> vision_intelligence.video_asr)."""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from vision_intelligence.video_asr.manifest import read_manifest

from vision_intelligence.video_asr.pipeline import _STAGE_ORDER

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


@router.get("/videos")
async def list_videos(request: Request) -> list[dict]:
    """List all processed videos."""
    st = request.app.state.video_asr_storage
    return await st.list_videos()


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


@router.get("/videos/{video_id}/progress")
async def video_progress(video_id: str, request: Request) -> EventSourceResponse:
    st = request.app.state.video_asr_storage
    settings = request.app.state.video_asr_settings

    async def generator():
        last_payload: str | None = None
        while True:
            if await request.is_disconnected():
                break
            conn = st._conn
            cur = await conn.execute(
                "SELECT stage, status, duration_sec, started_at, finished_at "
                "FROM pipeline_runs WHERE video_id = ? ORDER BY started_at",
                (video_id,),
            )
            rows = await cur.fetchall()
            stages = [
                {"stage": r[0], "status": r[1], "duration_sec": r[2], "started_at": r[3]}
                for r in rows
            ]

            video_dir = Path(settings.output_root) / video_id
            chunks_dir = video_dir / "chunks"

            total_chunks = None
            pm = read_manifest(video_dir, "preprocess")
            if pm is not None:
                boundaries = (pm.extra or {}).get("boundaries")
                if boundaries is not None:
                    total_chunks = len(boundaries)

            chunk_info = []
            retrying_chunks: list[dict] = []
            if chunks_dir.exists():
                for p in sorted(
                    p for p in chunks_dir.glob("chunk_???.json")
                    if p.stem.count('_') == 1
                ):
                    try:
                        head = p.read_bytes()[:256].decode("utf-8", errors="replace")
                        m = re.search(r'"asr_engine"\s*:\s*"([^"]*)"', head)
                        engine = m.group(1) if m else ""
                        chunk_idx = int(p.stem.split('_')[1])
                        chunk_info.append({"id": chunk_idx, "engine": engine})
                    except Exception:
                        pass
                for p in chunks_dir.glob("chunk_???.retry"):
                    try:
                        import json as _json
                        retry_data = _json.loads(p.read_text(encoding="utf-8"))
                        chunk_idx = int(p.stem.split('_')[1])
                        retrying_chunks.append({"id": chunk_idx, **retry_data})
                    except Exception:
                        pass

            transcribe_progress = {"done": len(chunk_info), "total": total_chunks, "chunks": chunk_info, "retrying": retrying_chunks}

            cur = await conn.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM llm_usage WHERE video_id = ?",
                (video_id,),
            )
            cost_row = await cur.fetchone()
            cost_usd = round(float(cost_row[0]) if cost_row else 0.0, 6)

            payload = json.dumps({
                "stages": stages,
                "transcribe_progress": transcribe_progress,
                "cost_usd": cost_usd,
            }, ensure_ascii=False)
            if payload != last_payload:
                last_payload = payload
                yield {"event": "progress", "data": payload}

            stage_statuses = {r["stage"]: r["status"] for r in stages}
            all_done = (
                len(stages) == len(_STAGE_ORDER)
                and all(stage_statuses.get(s) in ("done", "failed") for s in _STAGE_ORDER)
            )
            if all_done:
                break

            await asyncio.sleep(2.0)

    return EventSourceResponse(generator())


@router.delete("/videos/{video_id}")
async def delete_video(video_id: str, request: Request) -> dict:
    import shutil
    st = request.app.state.video_asr_storage
    settings = request.app.state.video_asr_settings
    conn = st._conn
    for table in ("transcript_segments", "transcript_fts", "pipeline_runs", "llm_usage", "asr_job_videos", "video_sources"):
        await conn.execute(f"DELETE FROM {table} WHERE video_id = ?", (video_id,))
    await conn.commit()
    video_dir = _video_dir(settings, video_id)
    if video_dir.exists():
        shutil.rmtree(video_dir)
    return {"deleted": video_id}


@router.get("/search")
async def search(request: Request, q: str, limit: int = 50) -> list[dict]:
    from vision_intelligence.video_asr.cleaning import jieba_tokenize
    st = request.app.state.video_asr_storage
    return await st.search_segments(jieba_tokenize(q), limit=limit)


class ImportToPlanBody(BaseModel):
    plan_id: str


@router.post("/videos/{video_id}/import-to-plan")
async def import_to_plan(video_id: str, body: ImportToPlanBody, request: Request) -> dict:
    st = getattr(request.app.state, "video_asr_storage", None)
    if st is None:
        raise HTTPException(503, "ASR storage not available")
    plan_store = getattr(request.app.state, "plan_store", None)
    if plan_store is None:
        raise HTTPException(503, "plan store not available")

    sp = await st.get_style_profile(video_id)
    if sp is None:
        raise HTTPException(404, "style profile not found — run analyze stage first")

    plan = await plan_store.get(body.plan_id)
    if plan is None:
        raise HTTPException(404, "plan not found")

    persona = dict(plan.get("persona") or {})
    existing_style = persona.get("style", "")
    new_tags = "、".join(sp.tone_tags) if sp.tone_tags else ""
    if new_tags:
        persona["style"] = f"{existing_style}、{new_tags}" if existing_style else new_tags

    existing_phrases = set(persona.get("catchphrases") or [])
    persona["catchphrases"] = list(existing_phrases | set(sp.catchphrases))

    segments = list((plan.get("script") or {}).get("segments") or [])
    existing_titles = {s.get("title") for s in segments}

    if sp.opening_hooks and "开场" not in existing_titles:
        segments.insert(0, {
            "id": f"seg-{uuid.uuid4().hex[:8]}",
            "title": "开场",
            "goal": "吸引观众注意，建立信任感",
            "duration": 120,
            "cue": list(sp.opening_hooks),
            "must_say": False,
            "keywords": [],
        })

    if sp.cta_patterns and "行动号召" not in existing_titles:
        segments.append({
            "id": f"seg-{uuid.uuid4().hex[:8]}",
            "title": "行动号召",
            "goal": "引导观众下单、点击购物车",
            "duration": 60,
            "cue": list(sp.cta_patterns),
            "must_say": False,
            "keywords": [],
        })

    updated = {
        **plan,
        "persona": persona,
        "script": {**(plan.get("script") or {}), "segments": segments},
    }
    await plan_store.update(body.plan_id, updated)
    return {"video_id": video_id, "plan_id": body.plan_id, "status": "merged"}
