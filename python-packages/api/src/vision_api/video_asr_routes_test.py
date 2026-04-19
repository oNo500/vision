"""HTTP contract tests for video-asr routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from vision_api.main import create_app


def _client(api_key: str = "test-key"):
    import os
    os.environ["VISION_API_KEY"] = api_key
    app = create_app()
    # Bypass lifespan: inject mock ASR state directly
    mock_storage = AsyncMock()
    mock_storage._conn = AsyncMock()
    mock_storage._conn.execute = AsyncMock(return_value=AsyncMock(fetchone=AsyncMock(return_value=None)))
    app.state.video_asr_storage = mock_storage
    app.state.video_asr_jm = MagicMock()
    app.state.video_asr_settings = MagicMock()
    return TestClient(app)


def test_post_jobs_requires_api_key():
    c = _client()
    r = c.post("/api/intelligence/video-asr/jobs", json={"urls": ["u"]})
    assert r.status_code == 401


def test_get_jobs_no_key_required():
    c = _client()
    r = c.get("/api/intelligence/video-asr/jobs/nope")
    assert r.status_code in (404, 200)
