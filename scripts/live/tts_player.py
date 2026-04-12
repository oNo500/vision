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


_SAMPLE_RATE = 24000
_TTS_MODEL = "gemini-2.5-flash-tts"


def _make_gemini_speak(
    voice: str = "Sulafat",
    audio_device: str | None = None,
) -> Callable[[str, str | None], None]:
    """Return a speak_fn backed by Cloud Text-to-Speech streaming API.

    Uses streaming_synthesize so audio playback begins on the first chunk,
    eliminating the multi-second wait of the non-streaming generate_content path.
    Audio is PCM 16-bit 24kHz mono, streamed to sounddevice in real time.

    Args:
        voice: Gemini TTS voice name (e.g. "Sulafat").
        audio_device: Output device name substring (e.g. "CABLE Input" for VB-Cable).
                      None uses the system default device.
    """
    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()

    # Resolve sounddevice output device index once at startup
    device_idx: int | None = None
    if audio_device:
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if audio_device.lower() in d["name"].lower() and d["max_output_channels"] > 0:
                    device_idx = i
                    break
            if device_idx is None:
                logger.warning("Audio device %r not found, using default", audio_device)
        except ImportError:
            pass

    def _speak(text: str, speech_prompt: str | None = None) -> None:
        prompt = speech_prompt or _DEFAULT_SPEECH_PROMPT
        config_req = texttospeech.StreamingSynthesizeRequest(
            streaming_config=texttospeech.StreamingSynthesizeConfig(
                voice=texttospeech.VoiceSelectionParams(
                    name=voice,
                    language_code="cmn-CN",
                    model_name=_TTS_MODEL,
                )
            )
        )

        def _requests():
            yield config_req
            yield texttospeech.StreamingSynthesizeRequest(
                input=texttospeech.StreamingSynthesisInput(
                    text=text,
                    prompt=prompt,
                )
            )

        try:
            import numpy as np
            import sounddevice as sd

            stream = sd.OutputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                device=device_idx,
            )
            stream.start()
            try:
                for response in client.streaming_synthesize(_requests()):
                    chunk = np.frombuffer(response.audio_content, dtype=np.int16)
                    stream.write(chunk)
            finally:
                stream.stop()
                stream.close()

        except ImportError:
            # sounddevice not available — collect all chunks then play via afplay
            chunks: list[bytes] = []
            for response in client.streaming_synthesize(_requests()):
                chunks.append(response.audio_content)
            _play_audio(b"".join(chunks), device=None)

        except Exception as e:
            logger.warning("Gemini streaming TTS failed, falling back to say: %s", e)
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
        elif os.environ.get("GOOGLE_CLOUD_PROJECT"):
            self._speak = _make_gemini_speak(audio_device=audio_device)
            device_info = f" → {audio_device}" if audio_device else ""
            logger.info("TTSPlayer using Gemini-2.5-Flash-TTS streaming (Sulafat%s)", device_info)
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
