"""TTSPlayer — async TTS queue consumer.

In development, accepts a ``speak_fn`` for easy mocking.
Default production backend: Gemini-2.5-Flash-TTS via Vertex AI (cmn-CN).
Fallback: macOS ``say`` command.
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _make_gemini_speak(project: str, voice: str = "Aoede", location: str = "us-central1") -> Callable[[str], None]:
    """Return a speak_fn backed by Gemini-2.5-Flash-TTS via Vertex AI.

    Audio is PCM 16-bit 24kHz mono; wrapped in a WAV and played via afplay.
    """
    import tempfile
    import wave

    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=project, location=location)

    def _speak(text: str) -> None:
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
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
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)   # 16-bit
                wf.setframerate(24000)
                wf.writeframes(audio_data)
            subprocess.run(["afplay", tmp_path], check=True)
        except Exception as e:
            logger.warning("Gemini TTS failed, falling back to say: %s", e)
            _fallback_speak(text)

    return _speak


def _fallback_speak(text: str) -> None:
    """macOS `say` fallback."""
    try:
        subprocess.run(["say", text], check=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("TTS fallback also failed: %s", e)


class TTSPlayer:
    """Consumes text items from a queue and speaks them one at a time.

    Args:
        in_queue: Queue of text strings to speak.
        speak_fn: Callable that blocks until speech is complete.
                  If None, uses Gemini-2.5-Flash-TTS when GOOGLE_CLOUD_PROJECT
                  is set, otherwise falls back to macOS ``say``.
    """

    def __init__(
        self,
        in_queue: queue.Queue[str],
        speak_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._queue = in_queue
        if speak_fn is not None:
            self._speak = speak_fn
        elif project := os.environ.get("GOOGLE_CLOUD_PROJECT"):
            self._speak = _make_gemini_speak(project)
            logger.info("TTSPlayer using Gemini-2.5-Flash-TTS (cmn-CN)")
        else:
            self._speak = _fallback_speak
            logger.info("TTSPlayer using macOS say fallback")
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
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            logger.info("[TTS] Speaking: %s", text[:60])
            with self._lock:
                self._is_speaking = True
            try:
                self._speak(text)
            finally:
                with self._lock:
                    self._is_speaking = False
                self._queue.task_done()
