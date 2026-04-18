"""Demucs BGM removal + ffmpeg chunk splitting."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _run_demucs(input_path: Path, output_path: Path) -> None:
    """Run demucs htdemucs; extract the 'vocals' stem to output_path."""
    tmp = output_path.parent / "_demucs_out"
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python", "-m", "demucs.separate",
         "-n", "htdemucs", "--two-stems=vocals",
         "-o", str(tmp), str(input_path)],
        capture_output=True, check=True,
    )
    found = list(tmp.rglob("vocals.wav"))
    if not found:
        raise RuntimeError(f"demucs did not produce vocals.wav in {tmp}")
    shutil.move(str(found[0]), str(output_path))
    shutil.rmtree(tmp, ignore_errors=True)


def _probe_duration(path: Path) -> float:
    """ffprobe duration in seconds."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def _run_ffmpeg_slice(input_path: Path, output_path: Path,
                     start: float, duration: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path),
         "-ss", str(start), "-t", str(duration),
         "-ac", "1", "-ar", "16000",
         str(output_path)],
        capture_output=True, check=True,
    )


def remove_bgm(audio_path: Path, vocals_out: Path) -> None:
    vocals_out.parent.mkdir(parents=True, exist_ok=True)
    _run_demucs(audio_path, vocals_out)


class split_into_chunks:
    @staticmethod
    def compute_boundaries(
        duration_sec: float, chunk_sec: int, overlap_sec: int,
    ) -> list[tuple[float, float]]:
        """Return list of (start, end) in seconds. Last chunk extends to duration.

        Chunks are placed at nominal positions 0, chunk_sec, 2*chunk_sec, ...
        Each chunk (except the first) starts overlap_sec before its nominal
        position so adjacent chunks share overlap_sec of audio context.
        The final chunk always ends at duration_sec.
        """
        boundaries: list[tuple[float, float]] = []
        i = 0
        while True:
            nominal_start = i * chunk_sec
            if nominal_start >= duration_sec:
                break
            start = max(0.0, nominal_start - overlap_sec) if i > 0 else 0.0
            nominal_end = (i + 1) * chunk_sec
            end = min(nominal_end, duration_sec)
            boundaries.append((start, end))
            if end >= duration_sec:
                break
            i += 1
        return boundaries


def preprocess_audio(
    audio_path: Path, vocals_out: Path, chunks_dir: Path,
    *, chunk_sec: int, overlap_sec: int, enable_bgm_removal: bool,
) -> dict:
    """Run the preprocess stage end-to-end. Return manifest-ready dict."""
    if enable_bgm_removal:
        remove_bgm(audio_path, vocals_out)
        source_for_chunks = vocals_out
    else:
        shutil.copy(audio_path, vocals_out)
        source_for_chunks = vocals_out

    duration = _probe_duration(source_for_chunks)
    boundaries = split_into_chunks.compute_boundaries(
        duration, chunk_sec, overlap_sec,
    )

    chunks_dir.mkdir(parents=True, exist_ok=True)
    for i, (start, end) in enumerate(boundaries):
        out = chunks_dir / f"chunk_{i:03d}.wav"
        _run_ffmpeg_slice(source_for_chunks, out, start, end - start)

    return {
        "bgm_removed": enable_bgm_removal,
        "chunk_count": len(boundaries),
        "chunk_duration_sec": chunk_sec,
        "chunk_overlap_sec": overlap_sec,
        "sample_rate": 16000,
        "channels": 1,
        "demucs_model": "htdemucs" if enable_bgm_removal else None,
        "boundaries": [list(b) for b in boundaries],
    }
