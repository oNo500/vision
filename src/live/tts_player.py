"""TTSPlayer — async TTS queue consumer.

In development, accepts a ``speak_fn`` for easy mocking.
Default production backend: Gemini-2.5-Flash-TTS via Cloud Text-to-Speech (cmn-CN).
Fallback: macOS ``say`` command.

Queue items are (text, speech_prompt) tuples; speech_prompt may be None.

Architecture (Gemini TTS path):
  A single streaming_synthesize gRPC session and a single sounddevice OutputStream
  run for the lifetime of the player.  All sentences are yielded into the same gRPC
  call, so only the very first sentence incurs the ~1.5s connection setup cost.
  Subsequent sentences play with only the natural ~120ms pause between them.

  Session lifecycle:
    start() → opens OutputStream + starts _run() thread
    _run()  → opens gRPC session, yields sentences from in_queue in real time
              → on error, closes gRPC + reopens (re-incurs one 1.5s penalty)
    stop()  → signals _run() to exit, closes OutputStream
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

_DEFAULT_SPEECH_PROMPT = "带货主播收到互动时真情流露的回应，语气自然有情绪起伏，像在跟朋友聊天"
_SAMPLE_RATE = 24000
_TTS_MODEL = "gemini-2.5-flash-tts"
_SENTINEL = object()   # put into in_queue to signal shutdown


def _play_audio(pcm_data: bytes, device_idx: int | None = None) -> None:
    """Play raw PCM via sounddevice (blocking)."""
    import numpy as np
    import sounddevice as sd
    audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(audio, samplerate=_SAMPLE_RATE, device=device_idx)
    sd.wait()


def _fallback_speak(text: str, _prompt=None) -> None:
    """macOS `say` fallback."""
    try:
        subprocess.run(["say", text], check=True, timeout=30)
    except Exception as e:
        logger.warning("TTS fallback failed: %s", e)


class TTSPlayer:
    """Consumes (text, speech_prompt) items from a queue and speaks them one at a time.

    In mock/dev mode, pass ``speak_fn`` to override TTS entirely.
    In production, set ``GOOGLE_CLOUD_PROJECT`` and sounddevice + numpy will be used
    with a persistent Gemini streaming session for gap-free playback.

    Args:
        in_queue:    Queue of (text, speech_prompt | None) tuples.
        speak_fn:    Override for all TTS.  If given, the persistent-session path
                     is skipped and each item is handled by speak_fn(text, prompt).
        audio_device: Sounddevice output device name substring.  None = default.
    """

    def __init__(
        self,
        in_queue: queue.Queue[tuple[str, str | None]],
        speak_fn: Callable[[str, str | None], None] | None = None,
        audio_device: str | None = None,
        on_play: Callable[[str, str | None], None] | None = None,
        google_cloud_project: str | None = None,
    ) -> None:
        self._queue = in_queue
        self._speak_fn = speak_fn          # None → use Gemini persistent session
        self._audio_device = audio_device
        self._on_play = on_play            # called just before each sentence is spoken
        # Prefer explicit project arg; fall back to env var for backwards compat
        self._google_cloud_project = google_cloud_project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._is_speaking = False
        self._lock = threading.Lock()

        if speak_fn is not None:
            logger.info("TTSPlayer using custom speak_fn")
        elif self._google_cloud_project:
            device_info = f" → {audio_device}" if audio_device else ""
            logger.info("TTSPlayer using Gemini-2.5-Flash-TTS persistent session (Sulafat%s)", device_info)
        else:
            logger.info("TTSPlayer using system TTS fallback")

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="TTSPlayer")
        self._thread.start()
        logger.info("TTSPlayer started")

    def stop(self) -> None:
        self._stop_event.set()
        # Unblock the queue.get() inside _run
        try:
            self._queue.put_nowait((_SENTINEL, None))
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=8)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_device_idx(self) -> int | None:
        if not self._audio_device:
            return None
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if self._audio_device.lower() in d["name"].lower() and d["max_output_channels"] > 0:
                    return i
        except Exception:
            pass
        logger.warning("Audio device %r not found, using default", self._audio_device)
        return None

    # ------------------------------------------------------------------
    # Mock / speak_fn path
    # ------------------------------------------------------------------

    def _run_with_speak_fn(self) -> None:
        """Simple loop used when a custom speak_fn is provided (mock/test)."""
        while not self._stop_event.is_set():
            try:
                text, speech_prompt = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if text is _SENTINEL:
                self._queue.task_done()
                break
            logger.info("[TTS] Speaking: %s", text[:60])
            if self._on_play:
                self._on_play(text, speech_prompt)
            with self._lock:
                self._is_speaking = True
            try:
                self._speak_fn(text, speech_prompt)
            finally:
                with self._lock:
                    self._is_speaking = False
                self._queue.task_done()
                logger.info("[TTS] Done speaking, queue size=%d", self._queue.qsize())

    # ------------------------------------------------------------------
    # Gemini persistent-session path
    # ------------------------------------------------------------------

    def _run_gemini(self) -> None:
        """Gemini TTS: single gRPC session + single OutputStream for all sentences.

        Architecture: _requests() generator reads directly from in_queue, so gRPC
        receives each sentence the moment it arrives — no intermediate _pipe buffer.
        This avoids the 5s idle timeout that fires when _pipe empties between sentences.
        """
        import numpy as np
        import sounddevice as sd
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()
        device_idx = self._resolve_device_idx()
        voice = "Sulafat"

        while not self._stop_event.is_set():
            # Each iteration = one gRPC session (restarted on error / after SENTINEL)
            sd_stream = sd.OutputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                device=device_idx,
                blocksize=960,
            )
            sd_stream.start()

            _session_done = threading.Event()
            error_holder: list[Exception | None] = [None]

            # _requests() drives the gRPC session from a background thread.
            # It reads directly from in_queue so gRPC never idles between sentences.
            def _requests(stop=self._stop_event):
                yield texttospeech.StreamingSynthesizeRequest(
                    streaming_config=texttospeech.StreamingSynthesizeConfig(
                        voice=texttospeech.VoiceSelectionParams(
                            name=voice,
                            language_code="cmn-CN",
                            model_name=_TTS_MODEL,
                        )
                    )
                )
                while not stop.is_set():
                    try:
                        text, speech_prompt = self._queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if text is _SENTINEL:
                        self._queue.task_done()
                        return
                    logger.info("[TTS] Speaking: %s", text[:60])
                    if self._on_play:
                        self._on_play(text, speech_prompt)
                    with self._lock:
                        self._is_speaking = True
                    yield texttospeech.StreamingSynthesizeRequest(
                        input=texttospeech.StreamingSynthesisInput(
                            text=text,
                            prompt=speech_prompt or _DEFAULT_SPEECH_PROMPT,
                        )
                    )
                    self._queue.task_done()
                    with self._lock:
                        self._is_speaking = False
                    logger.info("[TTS] Done speaking, queue size=%d", self._queue.qsize())

            def _consume(holder=error_holder):
                try:
                    for response in client.streaming_synthesize(_requests()):
                        chunk = np.frombuffer(response.audio_content, dtype=np.int16)
                        sd_stream.write(chunk)
                except Exception as e:
                    holder[0] = e
                finally:
                    _session_done.set()

            consumer = threading.Thread(target=_consume, daemon=True, name="TTSConsumer")
            consumer.start()
            _session_done.wait()

            sd_stream.stop()
            sd_stream.close()

            if error_holder[0] and not self._stop_event.is_set():
                logger.warning("TTS session error: %s — restarting", error_holder[0])
                self._stop_event.wait(timeout=1.0)

    # ------------------------------------------------------------------
    # Fallback path (no GCP project)
    # ------------------------------------------------------------------

    def _run_fallback(self) -> None:
        while not self._stop_event.is_set():
            try:
                text, speech_prompt = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if text is _SENTINEL:
                self._queue.task_done()
                break
            logger.info("[TTS] Speaking: %s", text[:60])
            if self._on_play:
                self._on_play(text, speech_prompt)
            with self._lock:
                self._is_speaking = True
            try:
                _fallback_speak(text, speech_prompt)
            finally:
                with self._lock:
                    self._is_speaking = False
                self._queue.task_done()
                logger.info("[TTS] Done speaking, queue size=%d", self._queue.qsize())

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def _run(self) -> None:
        if self._speak_fn is not None:
            self._run_with_speak_fn()
        elif self._google_cloud_project:
            try:
                import sounddevice  # noqa: F401
                import numpy  # noqa: F401
                self._run_gemini()
            except ImportError:
                logger.warning("sounddevice/numpy not available, using fallback TTS")
                self._run_fallback()
            except Exception as e:
                logger.error("Gemini TTS session fatal error: %s", e)
                self._run_fallback()
        else:
            self._run_fallback()
