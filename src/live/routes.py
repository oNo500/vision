"""FastAPI router for the /live domain."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.deps import get_db, get_event_bus, get_session_manager
from src.api.settings import get_settings
from src.live.session import SessionAlreadyRunningError, SessionManager
from src.shared.db import Database
from src.shared.event_bus import EventBus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live")


class StartRequest(BaseModel):
    script: str | None = None
    product: str | None = None
    mock: bool = False
    project: str | None = None


class InjectRequest(BaseModel):
    content: str
    speech_prompt: str | None = None


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
