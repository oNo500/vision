"""TTSPlayer — async TTS queue consumer.

In development, accepts a ``speak_fn`` for easy mocking.
Default production backend: Gemini-2.5-Flash-TTS via Vertex AI (cmn-CN).
Fallback: macOS ``say`` command.

Queue items are (text, speech_prompt) tuples; speech_prompt may be None.
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import tempfile
import threading
import wave
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Default speech style used when LLM does not provide one
_DEFAULT_SPEECH_PROMPT = "带货主播收到互动时真情流露的回应，语气自然有情绪起伏，像在跟朋友聊天"


def _play_audio(pcm_data: bytes, device: str | None = None) -> None:
    """Play raw PCM 16-bit 24kHz mono audio, optionally to a named output device.

    Uses sounddevice when available (cross-platform, supports device selection).
    Falls back to afplay on macOS or winsound on Windows.

    Args:
        pcm_data: Raw PCM bytes (16-bit signed, 24000 Hz, mono).
        device: Output device name substring, e.g. "CABLE Input" for VB-Cable.
                None means the system default device.
    """
    try:
        import numpy as np
        import sounddevice as sd

        audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        device_idx: int | None = None
        if device:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if device.lower() in d["name"].lower() and d["max_output_channels"] > 0:
                    device_idx = i
                    break
            if device_idx is None:
                logger.warning("Audio device %r not found, using default", device)
        sd.play(audio, samplerate=24000, device=device_idx)
        sd.wait()
        return
    except ImportError:
        pass

    # sounddevice not available — fall back to file-based playback
    import sys
    import tempfile
    import wave as wave_mod

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    with wave_mod.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)

    if sys.platform == "darwin":
        subprocess.run(["afplay", tmp_path], check=True)
    elif sys.platform == "win32":
        import winsound
        winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
    else:
        subprocess.run(["aplay", tmp_path], check=True)


def _make_gemini_speak(
    project: str,
    voice: str = "Sulafat",
    location: str = "us-central1",
    audio_device: str | None = None,
) -> Callable[[str, str | None], None]:
    """Return a speak_fn backed by Gemini-2.5-Flash-TTS via Vertex AI.

    Audio is PCM 16-bit 24kHz mono, played via sounddevice (cross-platform).

    Args:
        project: GCP project ID.
        voice: Gemini TTS voice name.
        location: Vertex AI region.
        audio_device: Output device name substring (e.g. "CABLE Input" for VB-Cable).
                      None uses the system default device.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=project, location=location)

    def _speak(text: str, speech_prompt: str | None = None) -> None:
        prompt = speech_prompt or _DEFAULT_SPEECH_PROMPT
        contents = f"{prompt}：{text}"
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                ),
            )
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            _play_audio(audio_data, device=audio_device)
        except Exception as e:
            logger.warning("Gemini TTS failed, falling back to say: %s", e)
            _fallback_speak(text, None)

    return _speak


def _fallback_speak(text: str, speech_prompt: str | None = None) -> None:
    """macOS `say` fallback (ignores speech_prompt)."""
    try:
        subprocess.run(["say", text], check=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("TTS fallback also failed: %s", e)


class TTSPlayer:
    """Consumes (text, speech_prompt) items from a queue and speaks them one at a time.

    Args:
        in_queue: Queue of (text, speech_prompt) tuples. speech_prompt may be None.
        speak_fn: Callable(text, speech_prompt) that blocks until speech completes.
                  If None, uses Gemini-2.5-Flash-TTS when GOOGLE_CLOUD_PROJECT
                  is set, otherwise falls back to system TTS.
        audio_device: Output device name substring (e.g. "CABLE Input" for VB-Cable).
                      Only used when speak_fn is None and Gemini TTS is active.
    """

    def __init__(
        self,
        in_queue: queue.Queue[tuple[str, str | None]],
        speak_fn: Callable[[str, str | None], None] | None = None,
        audio_device: str | None = None,
    ) -> None:
        self._queue = in_queue
        if speak_fn is not None:
            self._speak = speak_fn
        elif project := os.environ.get("GOOGLE_CLOUD_PROJECT"):
            self._speak = _make_gemini_speak(project, audio_device=audio_device)
            device_info = f" → {audio_device}" if audio_device else ""
            logger.info("TTSPlayer using Gemini-2.5-Flash-TTS (Sulafat%s)", device_info)
        else:
            self._speak = _fallback_speak
            logger.info("TTSPlayer using system TTS fallback")
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._is_speaking = False
        self._lock = threading.Lock()

    @property
    def is_speaking(self) -> bool:
        """True while a TTS item is being spoken."""
        with self._lock:
            return self._is_speaking

    def start(self) -> None:
        """Start the consumer thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="TTSPlayer")
        self._thread.start()
        logger.info("TTSPlayer started")

    def stop(self) -> None:
        """Stop the consumer thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                text, speech_prompt = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            logger.info("[TTS] Speaking: %s", text[:60])
            with self._lock:
                self._is_speaking = True
            try:
                self._speak(text, speech_prompt)
            finally:
                with self._lock:
                    self._is_speaking = False
                self._queue.task_done()
