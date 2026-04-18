"""FastAPI routes for /live/plans/{plan_id}/rag — talk-points maintenance UI."""
from __future__ import annotations

import logging
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import Response

from src.live import rag_cli

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live/plans/{plan_id}/rag")


_KNOWN_CATEGORIES = ("scripts", "competitor_clips", "product_manual", "qa_log")
_ALLOWED_SUFFIXES = (".md", ".txt")
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # 5 MB
_FILENAME_SAFE_RE = re.compile(r"[^a-zA-Z0-9\u4e00-\u9fa5._-]")


def _sanitize_filename(name: str) -> str:
    """Strip any directory components and unsafe characters."""
    bare = Path(name).name   # drops .. / abs paths
    return _FILENAME_SAFE_RE.sub("_", bare)


def _check_plan_path(path: Path, data_root: Path) -> None:
    """Raise 400 if the resolved path escapes data_root."""
    try:
        path.resolve().relative_to(data_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid path")


# Indirection so tests can monkeypatch without touching rag_cli global.
def _run_build(plan_id: str) -> int:
    return rag_cli.cmd_build(plan_id)


def _build_state(app_state) -> dict:
    if not hasattr(app_state, "rag_builds"):
        app_state.rag_builds = {}
    return app_state.rag_builds


def _run_build_sync(request: Request, plan_id: str) -> None:
    state = _build_state(request.app.state)
    state[plan_id] = {"running": True, "last_build_time": None, "last_error": None}
    try:
        _run_build(plan_id)
        state[plan_id] = {
            "running": False,
            "last_build_time": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        }
    except Exception as e:
        logger.exception("RAG build failed for plan %s", plan_id)
        state[plan_id] = {
            "running": False,
            "last_build_time": state[plan_id].get("last_build_time"),
            "last_error": f"{e}\n{traceback.format_exc()}"[:1000],
        }


# ---------------------------------------------------------------------------
# GET /  — status
# ---------------------------------------------------------------------------


@router.get("/")
def get_status(plan_id: str) -> dict:
    plan_root = rag_cli.DATA_ROOT / plan_id
    index_root = rag_cli.INDEX_ROOT / plan_id
    meta_path = index_root / "meta.json"

    meta = rag_cli._load_meta(meta_path)
    meta_sources = meta.get("sources", {})

    sources_on_disk = []
    current_hashes: dict[str, str] = {}
    if plan_root.is_dir():
        for src in rag_cli._scan_sources(plan_root):
            h = rag_cli._compute_file_hash(src.path)
            current_hashes[src.rel_path] = h
            indexed_entry = meta_sources.get(src.rel_path)
            sources_on_disk.append({
                "rel_path": src.rel_path,
                "category": src.category,
                "chunks": (indexed_entry or {}).get("chunks", 0),
                "sha256": h,
                "indexed": bool(indexed_entry and indexed_entry.get("sha256") == h),
            })

    indexed = bool(meta) and (
        (index_root / "chroma.sqlite3").exists()
        or (index_root / "chroma.sqlite").exists()
    )

    # dirty = any file missing from meta, sha mismatch, or meta source gone from disk
    added_or_changed, removed = rag_cli._diff_sources(meta_sources, current_hashes)
    dirty = bool(added_or_changed or removed)

    return {
        "indexed": indexed,
        "dirty": dirty,
        "chunk_count": meta.get("chunk_count", 0),
        "build_time": meta.get("build_time"),
        "file_count": len(sources_on_disk),
        "sources": sources_on_disk,
    }


# ---------------------------------------------------------------------------
# POST /files — upload
# ---------------------------------------------------------------------------


@router.post("/files", status_code=201)
async def upload_file(
    plan_id: str,
    category: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if category not in _KNOWN_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"category must be one of {_KNOWN_CATEGORIES}",
        )

    raw_name = file.filename or ""
    suffix = Path(raw_name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"only {_ALLOWED_SUFFIXES} allowed",
        )

    safe_name = _sanitize_filename(raw_name)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="file exceeds 5MB limit")

    plan_root = rag_cli.DATA_ROOT / plan_id
    target_dir = plan_root / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    _check_plan_path(target, plan_root)

    overwritten = target.exists()
    target.write_bytes(content)

    rel_path = f"{category}/{safe_name}"
    return {"rel_path": rel_path, "category": category, "overwritten": overwritten}


# ---------------------------------------------------------------------------
# DELETE /files/{category}/{filename}
# ---------------------------------------------------------------------------


@router.delete("/files/{category}/{filename}", status_code=204)
def delete_file(plan_id: str, category: str, filename: str) -> Response:
    if category not in _KNOWN_CATEGORIES:
        raise HTTPException(status_code=400, detail="unknown category")

    safe_name = _sanitize_filename(filename)
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="invalid filename")

    plan_root = rag_cli.DATA_ROOT / plan_id
    target = plan_root / category / safe_name
    _check_plan_path(target, plan_root)

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    target.unlink()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /rebuild + GET /rebuild/status
# ---------------------------------------------------------------------------


@router.post("/rebuild", status_code=202)
def trigger_rebuild(
    plan_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    state = _build_state(request.app.state)
    existing = state.get(plan_id)
    if existing and existing.get("running"):
        raise HTTPException(status_code=409, detail="build already running")

    background_tasks.add_task(_run_build_sync, request, plan_id)
    return {"scheduled": True}


@router.get("/rebuild/status")
def rebuild_status(plan_id: str, request: Request) -> dict:
    state = _build_state(request.app.state)
    entry = state.get(plan_id) or {
        "running": False,
        "last_build_time": None,
        "last_error": None,
    }
    return entry
