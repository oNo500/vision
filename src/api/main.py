"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.settings import get_settings
from src.live.routes import router as live_router
from src.live.plan_routes import router as plan_router
from src.live.rag_routes import router as rag_router
from vision_shared.db import Database
from vision_shared.event_bus import EventBus
from src.live.session import SessionManager
from src.live.danmaku_manager import DanmakuManager

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()
        app.state.event_bus = EventBus(loop)
        app.state.db = Database(settings.vision_db_path)
        await app.state.db.init()
        app.state.session_manager = SessionManager(app.state.event_bus)
        app.state.danmaku_manager = DanmakuManager(app.state.event_bus)
        app.state.rag_builds = {}
        logger.info("Vision API started")
        yield
        await app.state.db.close()
        logger.info("Vision API stopped")

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(live_router)
    app.include_router(plan_router)
    app.include_router(rag_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "healthy"}

    return app


app = create_app()
