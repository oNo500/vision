"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vision_api.api_key import ApiKeyMiddleware
from vision_api.settings import get_settings
from vision_live.routes import router as live_router
from vision_live.plan_routes import router as plan_router
from vision_live.rag_routes import router as rag_router
from vision_live.plan_store import PlanStore
from vision_shared.db import Database
from vision_shared.event_bus import EventBus
from vision_live.session import SessionManager
from vision_live.danmaku_manager import DanmakuManager

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()
        app.state.event_bus = EventBus(loop)
        app.state.db = Database(settings.vision_db_path)
        await app.state.db.init()
        app.state.plan_store = PlanStore(app.state.db.conn)
        app.state.session_manager = SessionManager(app.state.event_bus)
        app.state.danmaku_manager = DanmakuManager(app.state.event_bus)
        app.state.rag_builds = {}
        logger.info("Vision API started")
        yield
        await app.state.db.close()
        logger.info("Vision API stopped")

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        ApiKeyMiddleware, api_key=settings.vision_api_key,
        protected_prefixes=("/api/intelligence/",),
    )

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


def run() -> None:
    """Console-script entry point: `uv run vision-api`."""
    import uvicorn

    uvicorn.run(
        "vision_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
