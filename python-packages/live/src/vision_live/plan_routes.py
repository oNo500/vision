"""FastAPI router for /live/plans — LivePlan CRUD."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.deps import get_plan_store, get_session_manager
from vision_live.plan_store import PlanStore
from vision_live.session import SessionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live/plans")


class ProductBody(BaseModel):
    name: str = ""
    description: str = ""
    price: str = ""
    highlights: list[str] = []
    faq: list[dict] = []


class PersonaBody(BaseModel):
    name: str = ""
    style: str = ""
    catchphrases: list[str] = []
    forbidden_words: list[str] = []


class SegmentBody(BaseModel):
    id: str
    title: str = ""
    goal: str = ""
    duration: int
    cue: list[str] = []
    must_say: bool = False
    keywords: list[str] = []


class ScriptBody(BaseModel):
    segments: list[SegmentBody] = []


class PlanBody(BaseModel):
    name: str
    product: ProductBody = ProductBody()
    persona: PersonaBody = PersonaBody()
    script: ScriptBody = ScriptBody()


@router.get("")
async def list_plans(store: PlanStore = Depends(get_plan_store)) -> list[dict]:
    return await store.list_all()


@router.post("", status_code=201)
async def create_plan(
    body: PlanBody,
    store: PlanStore = Depends(get_plan_store),
) -> dict:
    return await store.create(body.model_dump())


@router.get("/active")
def get_active_plan(sm: SessionManager = Depends(get_session_manager)) -> dict:
    return {"plan": sm.get_active_plan()}


@router.get("/{plan_id}")
async def get_plan(
    plan_id: str,
    store: PlanStore = Depends(get_plan_store),
) -> dict:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/{plan_id}")
async def update_plan(
    plan_id: str,
    body: PlanBody,
    store: PlanStore = Depends(get_plan_store),
) -> dict:
    updated = await store.update(plan_id, body.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: str,
    store: PlanStore = Depends(get_plan_store),
    sm: SessionManager = Depends(get_session_manager),
) -> Response:
    active = sm.get_active_plan()
    if active and active.get("id") == plan_id:
        raise HTTPException(status_code=409, detail="Cannot delete the currently loaded plan")
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    await store.delete(plan_id)
    return Response(status_code=204)


@router.post("/{plan_id}/load")
async def load_plan(
    plan_id: str,
    store: PlanStore = Depends(get_plan_store),
    sm: SessionManager = Depends(get_session_manager),
) -> dict:
    if sm.get_state().get("running"):
        raise HTTPException(
            status_code=409,
            detail="Session is running, stop it before loading a new plan",
        )
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    sm.load_plan(plan)
    return {"plan": plan}
