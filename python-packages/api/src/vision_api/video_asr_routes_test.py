"""HTTP contract tests for video-asr routes."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from vision_api.main import create_app


def _client(api_key: str = "test-key"):
    os.environ["VISION_API_KEY"] = api_key
    app = create_app()
    # Bypass lifespan: inject mock ASR state directly
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=AsyncMock(fetchone=AsyncMock(return_value=None), fetchall=AsyncMock(return_value=[])))
    mock_conn.commit = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage._conn = mock_conn
    app.state.video_asr_storage = mock_storage
    app.state.video_asr_jm = MagicMock()
    app.state.video_asr_settings = MagicMock()
    return TestClient(app)



def test_get_jobs_no_key_required():
    c = _client()
    r = c.get("/api/intelligence/video-asr/jobs/nope")
    assert r.status_code in (404, 200)


def test_list_videos_empty():
    c = _client()
    c.app.state.video_asr_storage.list_videos = AsyncMock(return_value=[])
    r = c.get("/api/intelligence/video-asr/videos")
    assert r.status_code == 200
    assert r.json() == []


def test_delete_video_removes_db_rows_and_files():
    c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        video_id = "BV1test"
        video_dir = Path(tmp) / video_id
        video_dir.mkdir()
        (video_dir / "transcript.md").write_text("hello")
        c.app.state.video_asr_settings.output_root = tmp

        r = c.delete(
            f"/api/intelligence/video-asr/videos/{video_id}",
            headers={"X-API-Key": "test-key"},
        )
        assert r.status_code == 200
        assert r.json() == {"deleted": video_id}
        assert not video_dir.exists()
        # commit was called
        c.app.state.video_asr_storage._conn.commit.assert_awaited()


def test_delete_video_nonexistent_dir_still_succeeds():
    c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        c.app.state.video_asr_settings.output_root = tmp
        r = c.delete(
            "/api/intelligence/video-asr/videos/ghost",
            headers={"X-API-Key": "test-key"},
        )
        assert r.status_code == 200
        assert r.json() == {"deleted": "ghost"}


def test_import_to_plan_merges_style_into_persona():
    c = _client()
    plan_id = "plan-abc"

    from vision_intelligence.video_asr.models import StyleProfile
    sp = StyleProfile(
        video_id="BV1test",
        host_speaking_ratio=0.8,
        speaker_count={"host": 100, "guest": 0, "other": 0, "unknown": 0},
        top_phrases=[],
        catchphrases=["买它", "OMG"],
        opening_hooks=["大家好欢迎来到直播间", "今天给大家带来一款好物"],
        cta_patterns=["现在下单立减", "库存不多了"],
        transition_patterns=[],
        sentence_length={"p50": 12.0, "p90": 25.0, "unit": "chars"},
        tone_tags=["热情", "煽动"],
        english_ratio=0.02,
    )
    c.app.state.video_asr_storage.get_style_profile = AsyncMock(return_value=sp)

    existing_plan = {
        "id": plan_id,
        "name": "测试方案",
        "product": {"name": "", "description": "", "price": "", "highlights": [], "faq": []},
        "persona": {"name": "", "style": "", "catchphrases": [], "forbidden_words": []},
        "script": {"segments": []},
    }
    from vision_live.plan_store import PlanStore
    mock_plan_store = AsyncMock(spec=PlanStore)
    mock_plan_store.get = AsyncMock(return_value=existing_plan)
    mock_plan_store.update = AsyncMock(return_value=existing_plan)
    c.app.state.plan_store = mock_plan_store

    r = c.post(
        "/api/intelligence/video-asr/videos/BV1test/import-to-plan",
        json={"plan_id": plan_id},
    )
    assert r.status_code == 200, r.text

    call_args = mock_plan_store.update.call_args
    updated = call_args[0][1]

    assert "热情" in updated["persona"]["style"]
    assert "煽动" in updated["persona"]["style"]
    assert "买它" in updated["persona"]["catchphrases"]
    assert "OMG" in updated["persona"]["catchphrases"]

    titles = [s["title"] for s in updated["script"]["segments"]]
    assert "开场" in titles
    assert "行动号召" in titles

    opening_seg = next(s for s in updated["script"]["segments"] if s["title"] == "开场")
    assert "大家好欢迎来到直播间" in opening_seg["cue"]

    cta_seg = next(s for s in updated["script"]["segments"] if s["title"] == "行动号召")
    assert "现在下单立减" in cta_seg["cue"]


def test_import_to_plan_404_if_no_style():
    c = _client()
    c.app.state.video_asr_storage.get_style_profile = AsyncMock(return_value=None)
    from vision_live.plan_store import PlanStore
    c.app.state.plan_store = AsyncMock(spec=PlanStore)
    r = c.post(
        "/api/intelligence/video-asr/videos/BV1ghost/import-to-plan",
        json={"plan_id": "plan-xyz"},
    )
    assert r.status_code == 404


def test_import_to_plan_404_if_no_plan():
    c = _client()
    from vision_intelligence.video_asr.models import StyleProfile
    sp = StyleProfile(
        video_id="BV1test",
        host_speaking_ratio=0.5,
        speaker_count={"host": 10, "guest": 0, "other": 0, "unknown": 0},
        top_phrases=[], catchphrases=[], opening_hooks=[], cta_patterns=[],
        transition_patterns=[], sentence_length={"p50": 10.0, "p90": 20.0, "unit": "chars"},
        tone_tags=[], english_ratio=0.0,
    )
    c.app.state.video_asr_storage.get_style_profile = AsyncMock(return_value=sp)

    from vision_live.plan_store import PlanStore
    mock_plan_store = AsyncMock(spec=PlanStore)
    mock_plan_store.get = AsyncMock(return_value=None)
    c.app.state.plan_store = mock_plan_store

    r = c.post(
        "/api/intelligence/video-asr/videos/BV1test/import-to-plan",
        json={"plan_id": "nonexistent"},
    )
    assert r.status_code == 404
