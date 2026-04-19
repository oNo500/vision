from pathlib import Path
from unittest.mock import patch
import pytest

from vision_intelligence.video_asr.preprocessor import (
    remove_bgm, split_into_chunks, preprocess_audio,
)


def test_split_math(tmp_path):
    duration_sec = 3600.0
    chunks = split_into_chunks.compute_boundaries(
        duration_sec, chunk_sec=1200, overlap_sec=10,
    )
    # 3600s / (1200 - 10 overlap) rounds to enough chunks covering end
    assert chunks[0] == (0.0, 1200.0)
    assert chunks[-1][1] >= 3600.0


def test_remove_bgm_calls_demucs(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake")
    vocals = tmp_path / "vocals.wav"
    with patch("vision_intelligence.video_asr.preprocessor._run_demucs") as m:
        def fake(input_path, output_path):
            Path(output_path).write_bytes(b"vocals")
        m.side_effect = fake
        remove_bgm(audio, vocals)
    assert vocals.exists()


def test_preprocess_audio_produces_chunks(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake")
    vocals = tmp_path / "vocals.wav"
    chunks_dir = tmp_path / "chunks"

    with patch("vision_intelligence.video_asr.preprocessor._run_demucs") as demucs_m, \
         patch("vision_intelligence.video_asr.preprocessor._run_ffmpeg_slice") as ffm_m, \
         patch("vision_intelligence.video_asr.preprocessor._probe_duration") as probe_m:
        demucs_m.side_effect = lambda i, o: Path(o).write_bytes(b"v")
        probe_m.return_value = 2400.0  # 40 min
        ffm_m.side_effect = lambda inp, out, start, dur: Path(out).write_bytes(b"c")

        result = preprocess_audio(
            audio, vocals, chunks_dir,
            chunk_sec=1200, overlap_sec=10, enable_bgm_removal=True,
        )

    assert result["bgm_removed"] is True
    assert result["chunk_count"] == 2
    assert vocals.exists()
    assert (chunks_dir / "chunk_000.wav").exists()
    assert (chunks_dir / "chunk_001.wav").exists()
