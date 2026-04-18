"""Integration tests for /live TTS routes (not covered by plan_routes_test)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def client(tmp_path):
    import os
    os.environ["VISION_DB_PATH"] = str(tmp_path / "test.db")
    from src.api.settings import get_settings
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
