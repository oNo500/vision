# python-packages/api/src/vision_api/rag_library_routes.py
"""FastAPI routes for /api/intelligence/rag-libraries."""
from __future__ import annotations

import logging
import re
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from vision_api.deps import get_rag_library_store
from vision_live import rag_cli
from vision_live.rag_library_store import RagLibraryStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence/rag-libraries")


class LibraryCreate(BaseModel):
    id: str
    name: str


class ImportTranscriptBody(BaseModel):
    video_id: str


def _build_state(app_state) -> dict:
    if not hasattr(app_state, "rag_builds"):
        app_state.rag_builds = {}
    return app_state.rag_builds


def _run_build_sync(request: Request, lib_id: str) -> None:
    state = _build_state(request.app.state)
    state[lib_id] = {"running": True, "last_build_time": None, "last_error": None}
    try:
        rag_cli.cmd_build(lib_id)
        state[lib_id] = {
            "running": False,
            "last_build_time": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        }
    except Exception as e:
        logger.exception("RAG build failed for library %s", lib_id)
        state[lib_id] = {
            "running": False,
            "last_build_time": state[lib_id].get("last_build_time"),
            "last_error": f"{e}\n{traceback.format_exc()}"[:1000],
        }


@router.get("/")
async def list_libraries(store: RagLibraryStore = Depends(get_rag_library_store)) -> list[dict]:
    return await store.list_all()


@router.post("/", status_code=201)
async def create_library(
    body: LibraryCreate,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", body.id):
        raise HTTPException(status_code=400, detail="id must be lowercase alphanumeric with hyphens")
    try:
        return await store.create(body.id, body.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/{lib_id}", status_code=204)
async def delete_library(
    lib_id: str,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> Response:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")
    await store.delete(lib_id)
    data_dir = rag_cli.DATA_ROOT / lib_id
    rag_dir = rag_cli.INDEX_ROOT / lib_id
    if data_dir.exists():
        shutil.rmtree(data_dir)
    if rag_dir.exists():
        shutil.rmtree(rag_dir)
    return Response(status_code=204)


@router.get("/{lib_id}/status")
def get_status(lib_id: str) -> dict:
    return rag_cli.get_plan_status(lib_id)


@router.post("/{lib_id}/files", status_code=201)
async def upload_file(
    lib_id: str,
    category: str = Form(...),
    file: UploadFile = File(...),
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")
    if category not in rag_cli.KNOWN_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {rag_cli.KNOWN_CATEGORIES}")
    raw_name = file.filename or ""
    suffix = Path(raw_name).suffix.lower()
    if suffix not in rag_cli.ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"only {rag_cli.ALLOWED_SUFFIXES} allowed")
    safe_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5._-]", "_", Path(raw_name).name)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file exceeds 5MB limit")
    target_dir = rag_cli.DATA_ROOT / lib_id / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    overwritten = target.exists()
    target.write_bytes(content)
    return {"rel_path": f"{category}/{safe_name}", "category": category, "overwritten": overwritten}


@router.delete("/{lib_id}/files/{category}/{filename}", status_code=204)
async def delete_file(
    lib_id: str,
    category: str,
    filename: str,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> Response:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")
    if category not in rag_cli.KNOWN_CATEGORIES:
        raise HTTPException(status_code=400, detail="unknown category")
    safe_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5._-]", "_", Path(filename).name)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    target = rag_cli.DATA_ROOT / lib_id / category / safe_name
    try:
        target.unlink()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="file not found") from None
    return Response(status_code=204)


@router.post("/{lib_id}/import-transcript")
async def import_transcript(
    lib_id: str,
    body: ImportTranscriptBody,
    request: Request,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")

    settings = request.app.state.video_asr_settings
    video_dir = Path(settings.output_root) / body.video_id
    transcript_md = video_dir / "transcript.md"
    summary_md = video_dir / "summary.md"

    if not transcript_md.exists():
        raise HTTPException(status_code=404, detail=f"transcript for video '{body.video_id}' not found")

    imported: list[str] = []

    dest_clips = rag_cli.DATA_ROOT / lib_id / "competitor_clips"
    dest_clips.mkdir(parents=True, exist_ok=True)
    clip_target = dest_clips / f"{body.video_id}.md"
    clip_target.write_bytes(transcript_md.read_bytes())
    imported.append(f"competitor_clips/{body.video_id}.md")

    if summary_md.exists():
        dest_scripts = rag_cli.DATA_ROOT / lib_id / "scripts"
        dest_scripts.mkdir(parents=True, exist_ok=True)
        script_target = dest_scripts / f"{body.video_id}_summary.md"
        script_target.write_bytes(summary_md.read_bytes())
        imported.append(f"scripts/{body.video_id}_summary.md")

    return {"imported": imported, "video_id": body.video_id}


@router.post("/{lib_id}/rebuild", status_code=202)
def trigger_rebuild(
    lib_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    state = _build_state(request.app.state)
    if state.get(lib_id, {}).get("running"):
        raise HTTPException(status_code=409, detail="build already running")
    background_tasks.add_task(_run_build_sync, request, lib_id)
    return {"scheduled": True}


@router.get("/{lib_id}/rebuild/status")
def rebuild_status(lib_id: str, request: Request) -> dict:
    state = _build_state(request.app.state)
    return state.get(lib_id) or {"running": False, "last_build_time": None, "last_error": None}
