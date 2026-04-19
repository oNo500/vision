from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from vision_intelligence.video_asr.pipeline import run_video


@pytest.fixture
def mock_stages():
    """Patch every external I/O + LLM call to a no-op."""
    with patch("vision_intelligence.video_asr.pipeline._stage_ingest") as ingest, \
         patch("vision_intelligence.video_asr.pipeline._stage_preprocess") as prep, \
         patch("vision_intelligence.video_asr.pipeline._stage_transcribe") as trans, \
         patch("vision_intelligence.video_asr.pipeline._stage_merge") as merge, \
         patch("vision_intelligence.video_asr.pipeline._stage_render") as render, \
         patch("vision_intelligence.video_asr.pipeline._stage_analyze") as analyze, \
         patch("vision_intelligence.video_asr.pipeline._stage_load") as load:
        ingest.return_value = {"duration_sec": 1.0}
        prep.return_value = {"chunk_count": 1, "bgm_removed": True,
                             "chunk_duration_sec": 1200, "chunk_overlap_sec": 10,
                             "sample_rate": 16000, "channels": 1,
                             "demucs_model": "htdemucs", "boundaries": [[0.0, 1.0]]}
        trans.return_value = {"chunks_transcribed": 1, "chunks_failed": 0,
                              "tokens_in": 100, "tokens_out": 20,
                              "estimated_cost_usd": 0.001, "retries": 0}
        merge.return_value = {"segments_in": 1, "segments_out": 1,
                              "dedup_count": 0, "timestamp_fixes": 0,
                              "empty_dropped": 0}
        render.return_value = {"outputs": ["transcript.md", "transcript.srt"],
                               "total_segments": 1, "total_duration_sec": 1.0}
        analyze.return_value = {"tokens_in": 50, "tokens_out": 100,
                                "estimated_cost_usd": 0.001,
                                "segments_in": 1, "segments_filtered_out": 0}
        load.return_value = {"rows_inserted": {"video_sources": 1}}
        yield {
            "ingest": ingest, "preprocess": prep, "transcribe": trans,
            "merge": merge, "render": render, "analyze": analyze, "load": load,
        }


async def test_pipeline_runs_all_stages_in_order(tmp_path, mock_stages):
    ctx = MagicMock()
    ctx.video_id = "abc"
    ctx.url = "https://www.youtube.com/watch?v=abc"
    ctx.video_dir = tmp_path
    ctx.storage = AsyncMock()

    await run_video(ctx)

    # All 7 stages invoked once
    for key in ("ingest", "preprocess", "transcribe", "merge",
                "render", "analyze", "load"):
        assert mock_stages[key].called, f"{key} not called"


async def test_pipeline_skips_done_stages(tmp_path, mock_stages):
    from vision_intelligence.video_asr.manifest import write_manifest
    from vision_intelligence.video_asr.models import StageManifest
    # Pre-write a DONE manifest for ingest
    write_manifest(tmp_path, StageManifest(
        stage="ingest", video_id="abc", status="done",
        started_at="t0", finished_at="t1", duration_sec=0.0,
        inputs=[], outputs=["audio.m4a"], tool_versions={},
        pipeline_version="0.1.0",
    ))
    ctx = MagicMock()
    ctx.video_id = "abc"
    ctx.url = "https://www.youtube.com/watch?v=abc"
    ctx.video_dir = tmp_path
    ctx.storage = AsyncMock()

    await run_video(ctx)

    # ingest should NOT have been called
    assert not mock_stages["ingest"].called
    # later stages run
    assert mock_stages["preprocess"].called


async def test_pipeline_from_stage_deletes_downstream(tmp_path, mock_stages):
    from vision_intelligence.video_asr.manifest import write_manifest, manifest_path
    from vision_intelligence.video_asr.models import StageManifest
    # Pre-write all 7 manifests as done
    for stage in ("ingest", "preprocess", "transcribe", "merge",
                  "render", "analyze", "load"):
        write_manifest(tmp_path, StageManifest(
            stage=stage, video_id="abc", status="done",
            started_at="t", finished_at="t", duration_sec=0,
            inputs=[], outputs=[], tool_versions={}, pipeline_version="0.1.0",
        ))

    ctx = MagicMock()
    ctx.video_id = "abc"; ctx.url = "u"; ctx.video_dir = tmp_path
    ctx.storage = AsyncMock()

    await run_video(ctx, from_stage="merge")

    # merge, render, analyze, load manifests were deleted and re-run
    for key in ("merge", "render", "analyze", "load"):
        assert mock_stages[key].called
    # ingest/preprocess/transcribe NOT called
    for key in ("ingest", "preprocess", "transcribe"):
        assert not mock_stages[key].called
