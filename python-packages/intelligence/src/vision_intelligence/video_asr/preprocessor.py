"""Demucs BGM removal + ffmpeg chunk splitting."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_demucs(input_path: Path, output_path: Path) -> None:
    """Run demucs htdemucs via Python API; write vocals with soundfile.

    Avoids torchaudio.save() entirely — soundfile uses libsndfile (pure C),
    so this works on Mac, Linux, and Windows without torchcodec.
    """
    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.audio import convert_audio
    from demucs.pretrained import get_model

    model = get_model("htdemucs")
    model.eval()

    # CUDA > MPS (shifts=1 broken on MPS) > CPU
    if torch.cuda.is_available():
        device = "cuda"
        shifts = 1
    elif torch.backends.mps.is_available():
        device = "mps"
        shifts = 0  # shifts=1 causes incorrect results on MPS
    else:
        device = "cpu"
        shifts = 1

    wav = _load_audio_ffmpeg(input_path, model.samplerate)
    wav = wav.unsqueeze(0)  # (1, channels, samples)

    with torch.no_grad():
        sources = apply_model(model, wav, device=device, shifts=shifts, split=True,
                              overlap=0.25, progress=False)[0]

    vocal_idx = model.sources.index("vocals")
    vocals = sources[vocal_idx]  # (channels, samples)

    # Resample to 16kHz mono for downstream chunks
    vocals_16k = convert_audio(vocals, model.samplerate, 16000, 1)
    audio_np = vocals_16k.squeeze(0).numpy().astype(np.float32)
    sf.write(str(output_path), audio_np, 16000, subtype="PCM_16")


def _load_audio_ffmpeg(path: Path, sample_rate: int):
    """Load audio file into a (channels, samples) float32 tensor via ffmpeg."""
    import numpy as np
    import torch

    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-f", "f32le", "-ar", str(sample_rate), "-ac", "2", "pipe:1"],
        capture_output=True, check=True,
    )
    audio = np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2).T  # (2, samples)
    return torch.from_numpy(audio.copy())


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
    import numpy as np
    import soundfile as sf
    vocals_out.parent.mkdir(parents=True, exist_ok=True)
    _run_demucs(audio_path, vocals_out)
    data, _ = sf.read(str(vocals_out), dtype="float32")
    rms = float(np.sqrt(np.mean(data ** 2)))
    if rms < 0.001:
        logger.warning(
            "demucs vocals energy very low (%.4f), BGM removal may have suppressed speech",
            rms,
        )


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
        # Skip demucs if vocals_out already exists (crash-resume checkpoint).
        if not vocals_out.exists():
            remove_bgm(audio_path, vocals_out)
        source_for_chunks = vocals_out
    else:
        if not vocals_out.exists():
            shutil.copy(audio_path, vocals_out)
        source_for_chunks = vocals_out

    duration = _probe_duration(source_for_chunks)
    boundaries = split_into_chunks.compute_boundaries(
        duration, chunk_sec, overlap_sec,
    )

    chunks_dir.mkdir(parents=True, exist_ok=True)
    for i, (start, end) in enumerate(boundaries):
        out = chunks_dir / f"chunk_{i:03d}.wav"
        if not out.exists():
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
