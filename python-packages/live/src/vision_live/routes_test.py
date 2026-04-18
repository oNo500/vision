"""Integration tests for /live TTS routes (not covered by plan_routes_test)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vision_api.main import create_app


@pytest.fixture
def client(tmp_path):
    import os
    os.environ["VISION_DB_PATH"] = str(tmp_path / "test.db")
    from vision_api.settings import get_settings
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    get_settings.cache_clear()


def test_tts_queue_snapshot_endpoint_returns_empty_when_not_running(client):
    """When no session is running, snapshot endpoint returns []."""
    response = client.get("/live/tts/queue/snapshot")
    assert response.status_code == 200
    assert response.json() == []


def test_delete_tts_queue_item_returns_404_when_not_running(client):
    response = client.delete("/live/tts/queue/any-id")
    assert response.status_code == 404


def test_patch_tts_queue_item_returns_404_when_not_running(client):
    response = client.patch("/live/tts/queue/any-id", json={"text": "new"})
    assert response.status_code == 404


def test_reorder_tts_queue_returns_400_when_not_running(client):
    response = client.post(
        "/live/tts/queue/reorder",
        json={"stage": "pending", "ids": []},
    )
    assert response.status_code == 400


def test_patch_tts_queue_requires_text(client):
    """Missing `text` in body → FastAPI 422."""
    response = client.patch("/live/tts/queue/x", json={})
    assert response.status_code == 422


def test_reorder_tts_queue_requires_stage_and_ids(client):
    response = client.post("/live/tts/queue/reorder", json={"stage": "pending"})
    assert response.status_code == 422
