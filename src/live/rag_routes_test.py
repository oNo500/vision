"""Tests for /live/plans/{plan_id}/rag/* routes.

Exercises the HTTP surface end-to-end via FastAPI TestClient with
isolated tmp DATA_ROOT / INDEX_ROOT, and stubs out the heavy
`cmd_build` so no model downloads happen.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.live import rag_cli, rag_routes


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build a minimal FastAPI app with the rag router + isolated roots."""
    data_root = tmp_path / "data" / "talk_points"
    index_root = tmp_path / ".rag"
    monkeypatch.setattr(rag_cli, "DATA_ROOT", data_root)
    monkeypatch.setattr(rag_cli, "INDEX_ROOT", index_root)
    # rag_routes re-reads DATA_ROOT/INDEX_ROOT through rag_cli, so the
    # monkeypatch above is enough.

    # Stub cmd_build so tests don't load torch / download bge-base.
    build_calls: list[str] = []

    def fake_build(plan_id: str) -> int:
        build_calls.append(plan_id)
        # Mimic a successful build by writing a meta file + a dummy chroma file.
        idx = index_root / plan_id
        idx.mkdir(parents=True, exist_ok=True)
        (idx / "chroma.sqlite3").write_text("stub", encoding="utf-8")
        sources = {}
        for f in (data_root / plan_id).rglob("*"):
            if f.is_file() and f.suffix in (".md", ".txt"):
                rel = f.relative_to(data_root / plan_id).as_posix()
                sources[rel] = {"sha256": rag_cli.compute_file_hash(f), "chunks": 1}
        meta = {
            "build_time": "2026-04-18T12:00:00Z",
            "chunk_count": len(sources),
            "embedder": "stub",
            "sources": sources,
        }
        rag_cli._save_meta(idx / "meta.json", meta)
        return 0

    monkeypatch.setattr(rag_routes, "_run_build", fake_build)

    app = FastAPI()
    app.state.rag_builds = {}
    app.include_router(rag_routes.router)

    with TestClient(app) as c:
        c._build_calls = build_calls   # type: ignore[attr-defined]
        yield c


# ---------------------------------------------------------------------------
# GET /rag
# ---------------------------------------------------------------------------


def test_get_status_on_empty_plan(client: TestClient):
    r = client.get("/live/plans/p1/rag/")
    assert r.status_code == 200
    data = r.json()
    assert data["indexed"] is False
    assert data["file_count"] == 0
    assert data["sources"] == []
    assert data["dirty"] is False


def test_get_status_after_upload_marks_dirty(client: TestClient):
    client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("a.md", b"hi", "text/markdown")},
    )
    r = client.get("/live/plans/p1/rag/")
    data = r.json()
    assert data["file_count"] == 1
    assert data["indexed"] is False
    assert data["dirty"] is True
    assert data["sources"][0]["indexed"] is False


def test_get_status_after_rebuild_not_dirty(client: TestClient):
    client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("a.md", b"hi", "text/markdown")},
    )
    client.post("/live/plans/p1/rag/rebuild")
    r = client.get("/live/plans/p1/rag/")
    data = r.json()
    assert data["indexed"] is True
    assert data["dirty"] is False
    assert data["chunk_count"] == 1


# ---------------------------------------------------------------------------
# POST /rag/files
# ---------------------------------------------------------------------------


def test_upload_file_saved_in_category(client: TestClient, tmp_path: Path):
    r = client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("opening.md", b"hello", "text/markdown")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["rel_path"] == "scripts/opening.md"
    assert body["overwritten"] is False

    saved = rag_cli.DATA_ROOT / "p1" / "scripts" / "opening.md"
    assert saved.read_text(encoding="utf-8") == "hello"


def test_upload_overwrites_existing(client: TestClient):
    for content in (b"v1", b"v2"):
        r = client.post(
            "/live/plans/p1/rag/files",
            data={"category": "scripts"},
            files={"file": ("a.md", content, "text/markdown")},
        )
    body = r.json()
    assert body["overwritten"] is True

    saved = rag_cli.DATA_ROOT / "p1" / "scripts" / "a.md"
    assert saved.read_bytes() == b"v2"


def test_upload_rejects_non_text_suffix(client: TestClient):
    r = client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_upload_rejects_unknown_category(client: TestClient):
    r = client.post(
        "/live/plans/p1/rag/files",
        data={"category": "unknown"},
        files={"file": ("a.md", b"x", "text/markdown")},
    )
    assert r.status_code == 400


def test_upload_rejects_path_traversal_filename(client: TestClient):
    r = client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("../../etc/passwd.md", b"x", "text/markdown")},
    )
    # Either 400 or filename got sanitised; both acceptable — verify path safe
    if r.status_code == 201:
        saved_rel = r.json()["rel_path"]
        assert ".." not in saved_rel
        assert saved_rel.startswith("scripts/")
    else:
        assert r.status_code == 400


def test_upload_rejects_over_5mb(client: TestClient):
    big = b"x" * (5 * 1024 * 1024 + 1)
    r = client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("big.md", big, "text/markdown")},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /rag/files/{category}/{filename}
# ---------------------------------------------------------------------------


def test_delete_removes_file(client: TestClient):
    client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("a.md", b"x", "text/markdown")},
    )
    r = client.delete("/live/plans/p1/rag/files/scripts/a.md")
    assert r.status_code == 204

    saved = rag_cli.DATA_ROOT / "p1" / "scripts" / "a.md"
    assert not saved.exists()


def test_delete_missing_returns_404(client: TestClient):
    r = client.delete("/live/plans/p1/rag/files/scripts/ghost.md")
    assert r.status_code == 404


def test_delete_rejects_path_traversal(client: TestClient):
    r = client.delete("/live/plans/p1/rag/files/scripts/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code in (400, 404)


# ---------------------------------------------------------------------------
# POST /rag/rebuild
# ---------------------------------------------------------------------------


def test_rebuild_schedules_build(client: TestClient):
    client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("a.md", b"x", "text/markdown")},
    )
    r = client.post("/live/plans/p1/rag/rebuild")
    assert r.status_code == 202

    # TestClient runs BackgroundTasks synchronously by the time the response
    # is returned, so the stub has already been called.
    assert "p1" in client._build_calls   # type: ignore[attr-defined]


def test_rebuild_conflict_when_already_running(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # Simulate "already running" by pre-populating app state.
    client.app.state.rag_builds["p1"] = {
        "running": True,
        "last_build_time": None,
        "last_error": None,
    }
    r = client.post("/live/plans/p1/rag/rebuild")
    assert r.status_code == 409


def test_rebuild_status_after_success(client: TestClient):
    client.post(
        "/live/plans/p1/rag/files",
        data={"category": "scripts"},
        files={"file": ("a.md", b"x", "text/markdown")},
    )
    client.post("/live/plans/p1/rag/rebuild")
    r = client.get("/live/plans/p1/rag/rebuild/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["last_error"] is None
    assert body["last_build_time"] is not None


def test_rebuild_status_idle_plan(client: TestClient):
    r = client.get("/live/plans/p1/rag/rebuild/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["last_build_time"] is None


def test_rebuild_status_captures_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def boom(_plan_id: str) -> int:
        raise RuntimeError("build failed")

    monkeypatch.setattr(rag_routes, "_run_build", boom)
    client.post("/live/plans/p1/rag/rebuild")
    r = client.get("/live/plans/p1/rag/rebuild/status")
    body = r.json()
    assert body["running"] is False
    assert "build failed" in body["last_error"]
