"""FastAPI router for the /live domain."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.deps import get_danmaku_manager, get_db, get_event_bus, get_session_manager
from src.api.settings import get_settings
from vision_live.danmaku_manager import DanmakuManager
from vision_live.session import SessionAlreadyRunningError, SessionManager
from vision_shared.db import Database
from vision_shared.event_bus import EventBus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live")


class StartRequest(BaseModel):
    script: str | None = None
    product: str | None = None
    mock: bool = False
    project: str | None = None
    cdp_url: str | None = None


class SessionStartRequest(BaseModel):
    script: str | None = None
    product: str | None = None
    mock: bool = False
    project: str | None = None


class DanmakuStartRequest(BaseModel):
    mock: bool = False
    cdp_url: str | None = None


class StrategyRequest(BaseModel):
    strategy: str


class InjectRequest(BaseModel):
    content: str
    speech_prompt: str | None = None


class EditTtsRequest(BaseModel):
    text: str
    speech_prompt: str | None = None


class ReorderTtsRequest(BaseModel):
    stage: str
    ids: list[str]


@router.post("/start")
def start(
    body: StartRequest,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    s = get_settings()
    try:
        sm.start(
            script_path=body.script or s.default_script_path,
            product_path=body.product or s.default_product_path,
            mock=body.mock,
            project=body.project or s.google_cloud_project,
            # cdp_url now belongs to DanmakuManager — use /live/danmaku/start
        )
    except SessionAlreadyRunningError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sm.get_state()


@router.post("/stop")
def stop(sm: SessionManager = Depends(get_session_manager)) -> dict:
    try:
        sm.stop()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sm.get_state()


@router.get("/state")
def state(sm: SessionManager = Depends(get_session_manager)) -> dict:
    return sm.get_state()


@router.get("/tts/queue/snapshot")
def tts_queue_snapshot(sm: SessionManager = Depends(get_session_manager)) -> list[dict]:
    """Return a snapshot of pending + synthesized TTS items.

    Used by the frontend to rehydrate pipeline state on SSE reconnect.
    Returns [] when no session is running.
    """
    return sm.get_tts_queue_snapshot()


@router.delete("/tts/queue/{item_id}")
def delete_tts_item(
    item_id: str,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    ok = sm.remove_tts(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found or session not running")
    return {"ok": True}


@router.patch("/tts/queue/{item_id}")
def edit_tts_item(
    item_id: str,
    body: EditTtsRequest,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    from vision_live.tts_mutations import UNSET

    body_dict = body.model_dump(exclude_unset=True)
    prompt = body_dict.get("speech_prompt", UNSET)
    ok = sm.edit_tts(item_id, body.text, prompt)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found or session not running")
    return {"ok": True}


@router.post("/tts/queue/reorder")
def reorder_tts_items(
    body: ReorderTtsRequest,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    ok = sm.reorder_tts(body.stage, body.ids)
    if not ok:
        raise HTTPException(status_code=400, detail="reorder rejected: stage unknown or ids mismatch")
    return {"ok": True}


@router.post("/inject")
def inject(
    body: InjectRequest,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    try:
        sm.inject(body.content, body.speech_prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/script/next")
def script_next(sm: SessionManager = Depends(get_session_manager)) -> dict:
    runner = sm.get_script_runner()
    if runner is None:
        raise HTTPException(status_code=400, detail="Session not running")
    runner.advance()
    return sm.get_state()


@router.post("/script/prev")
def script_prev(sm: SessionManager = Depends(get_session_manager)) -> dict:
    runner = sm.get_script_runner()
    if runner is None:
        raise HTTPException(status_code=400, detail="Session not running")
    runner.rewind()
    return sm.get_state()


@router.get("/stream")
async def stream(bus: EventBus = Depends(get_event_bus)):
    q = bus.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping', 'ts': time.time()})}\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history")
async def history(
    limit: int = Query(default=100, ge=1, le=500),
    type_filter: str | None = Query(default=None, alias="type"),
    db: Database = Depends(get_db),
) -> list[dict]:
    return await db.get_history(limit=limit, type_filter=type_filter)


@router.post("/session/start")
def session_start(
    body: SessionStartRequest,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    s = get_settings()
    try:
        sm.start(
            script_path=body.script or s.default_script_path,
            product_path=body.product or s.default_product_path,
            mock=body.mock,
            project=body.project or s.google_cloud_project,
        )
    except SessionAlreadyRunningError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sm.get_state()


@router.post("/session/stop")
def session_stop(sm: SessionManager = Depends(get_session_manager)) -> dict:
    try:
        sm.stop()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sm.get_state()


@router.get("/session/state")
def session_state(sm: SessionManager = Depends(get_session_manager)) -> dict:
    return sm.get_state()


@router.post("/danmaku/start")
def danmaku_start(
    body: DanmakuStartRequest,
    sm: SessionManager = Depends(get_session_manager),
    dm: DanmakuManager = Depends(get_danmaku_manager),
) -> dict:
    s = get_settings()
    tts_queue = sm.get_tts_queue()
    urgent_queue = sm.get_urgent_queue()
    try:
        dm.start(
            mock=body.mock,
            cdp_url=body.cdp_url or s.cdp_url,
            tts_queue=tts_queue,
            get_strategy_fn=sm.get_strategy,
            urgent_queue=urgent_queue,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dm.get_state()


@router.post("/danmaku/stop")
def danmaku_stop(dm: DanmakuManager = Depends(get_danmaku_manager)) -> dict:
    try:
        dm.stop()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dm.get_state()


@router.get("/danmaku/state")
def danmaku_state(dm: DanmakuManager = Depends(get_danmaku_manager)) -> dict:
    return dm.get_state()


@router.get("/strategy")
def get_strategy(sm: SessionManager = Depends(get_session_manager)) -> dict:
    return {"strategy": sm.get_strategy()}


@router.post("/strategy")
def set_strategy(
    body: StrategyRequest,
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    try:
        sm.set_strategy(body.strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"strategy": sm.get_strategy()}
