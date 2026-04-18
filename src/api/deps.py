"""FastAPI dependency injection helpers."""
from __future__ import annotations

from fastapi import Request
from src.live.danmaku_manager import DanmakuManager
from src.live.session import SessionManager
from vision_shared.db import Database
from vision_shared.event_bus import EventBus


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


def get_danmaku_manager(request: Request) -> DanmakuManager:
    return request.app.state.danmaku_manager


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_plan_store(request: Request):
    return request.app.state.db.plan_store
