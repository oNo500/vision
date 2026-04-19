"""Tests for rag_library_routes import-transcript endpoint."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from vision_api.main import create_app


def _client():
    os.environ["VISION_API_KEY"] = ""
    app = create_app()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value={"id": "test-lib", "name": "Test"})
    app.state.rag_library_store = mock_store
    mock_asr_settings = MagicMock()
    app.state.video_asr_settings = mock_asr_settings
    # inject asr storage with segments
    mock_asr_storage = AsyncMock()
    app.state.video_asr_storage = mock_asr_storage
    return app, TestClient(app)


def test_import_transcript_uses_db_segments():
    """import-transcript should write host segments from DB, not transcript.md."""
    app, c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        app.state.video_asr_settings.output_root = tmp
        # No transcript.md in tmp — if old code path runs it would 404
        app.state.video_asr_storage.get_host_segments = AsyncMock(return_value=[
            {"start": 0.0, "end": 5.0, "text": "大家好欢迎来到直播间"},
            {"start": 5.5, "end": 10.0, "text": "今天给大家介绍这款产品"},
        ])

        with patch("vision_live.rag_cli.DATA_ROOT", Path(tmp) / "data"):
            r = c.post(
                "/api/intelligence/rag-libraries/test-lib/import-transcript",
                json={"video_id": "BV1test"},
            )

        assert r.status_code == 200
        data = r.json()
        assert "competitor_clips/BV1test.md" in data["imported"]

        # verify file written with host content
        md_path = Path(tmp) / "data" / "test-lib" / "competitor_clips" / "BV1test.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "大家好欢迎来到直播间" in content
        assert "今天给大家介绍这款产品" in content


def test_import_transcript_empty_segments_still_writes_file():
    """If no host segments in DB, writes empty file without error."""
    app, c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        app.state.video_asr_settings.output_root = tmp
        app.state.video_asr_storage.get_host_segments = AsyncMock(return_value=[])

        with patch("vision_live.rag_cli.DATA_ROOT", Path(tmp) / "data"):
            r = c.post(
                "/api/intelligence/rag-libraries/test-lib/import-transcript",
                json={"video_id": "BV1empty"},
            )

        assert r.status_code == 200
        assert "competitor_clips/BV1empty.md" in r.json()["imported"]


def test_import_transcript_copies_summary_if_exists():
    """If summary.md exists in output_root/video_id/, it is copied to scripts/."""
    app, c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        app.state.video_asr_settings.output_root = tmp
        app.state.video_asr_storage.get_host_segments = AsyncMock(return_value=[])

        # create summary.md
        summary_dir = Path(tmp) / "BV1summary"
        summary_dir.mkdir()
        (summary_dir / "summary.md").write_text("# Summary\n内容摘要", encoding="utf-8")

        with patch("vision_live.rag_cli.DATA_ROOT", Path(tmp) / "data"):
            r = c.post(
                "/api/intelligence/rag-libraries/test-lib/import-transcript",
                json={"video_id": "BV1summary"},
            )

        assert r.status_code == 200
        imported = r.json()["imported"]
        assert "competitor_clips/BV1summary.md" in imported
        assert "scripts/BV1summary_summary.md" in imported

        script_path = Path(tmp) / "data" / "test-lib" / "scripts" / "BV1summary_summary.md"
        assert script_path.exists()
        assert "内容摘要" in script_path.read_text(encoding="utf-8")
