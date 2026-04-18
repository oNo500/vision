"""TTSPlayer — two-stage TTS pipeline with auditable queue.

Architecture:
  in_queue (TtsItem)  →  synthesize thread  →  pcm_queue (PcmItem)  →  playback thread
                                                                          ↓
                                                               continuous OutputStream
                                                               (no stop/start = no artifacts)

Each TtsItem has a stable UUID so the front-end can display, edit, or delete
pending sentences before they are synthesized or played.

Events fired via on_queued / on_play / on_done callbacks (wired by SessionManager
to the EventBus so the front-end receives SSE updates).
"""
from __future__ import annotations

import dataclasses
import logging
import os
import queue
import subprocess
import threading
import uuid
from collections.abc import Callable

from vision_shared.ordered_item_store import OrderedItemStore

logger = logging.getLogger(__name__)

_DEFAULT_SPEECH_PROMPT = "带货主播收到互动时真情流露的回应，语气自然有情绪起伏，像在跟朋友聊天"
_SAMPLE_RATE = 24000
_SILENCE_FRAMES = 480    # 20ms micro-gap between sentences (at 24 kHz)
_FADE_FRAMES = 240       # 10ms fade-in/out to avoid click/pop at splice boundaries
_SENTINEL = object()


@dataclasses.dataclass
class TtsItem:
    id: str
    text: str
    speech_prompt: str | None
    stage: str = "pending"       # "pending" | "synthesized"
    urgent: bool = False
    cancel_flag: bool = False    # set by remove() when the item is in-flight

    @staticmethod
    def create(text: str, speech_prompt: str | None, urgent: bool = False) -> "TtsItem":
        return TtsItem(
            id=str(uuid.uuid4()),
            text=text,
            speech_prompt=speech_prompt,
            urgent=urgent,
        )


@dataclasses.dataclass
class PcmItem:
    id: str
    text: str
    speech_prompt: str | None
    pcm: "np.ndarray"  # float32, shape (N,)
    duration: float
    stage: str = "synthesized"
    urgent: bool = False


def _fallback_speak(text: str, _prompt: str | None = None) -> None:
    """macOS `say` fallback."""
    try:
        subprocess.run(["say", text], check=True, timeout=30)
    except Exception as e:
        logger.warning("TTS fallback failed: %s", e)


class TTSPlayer:
    """Two-stage TTS: synthesize thread + continuous playback thread.

    The in_queue holds TtsItem objects (text + id).  The synthesize thread
    converts each to PCM and puts PcmItem into pcm_queue.  The playback thread
    reads pcm_queue and writes into a continuously-open OutputStream so there
    are no start/stop artifacts between sentences.

    Args:
        in_queue:         Queue[TtsItem] — fed by DirectorAgent / inject.
        speak_fn:         Override for mock/test; skips synthesis entirely.
        audio_device:     Sounddevice output device name substring.
        on_queued:        Called when a TtsItem enters in_queue (for SSE).
        on_synthesized:   Called after a TtsItem has been converted to PCM and entered pcm_queue.
        on_play:          Called just before a sentence starts playing.
        on_done:          Called after a sentence finishes playing.
        google_cloud_project: GCP project for Cloud TTS.
    """

    def __init__(
        self,
        in_queue: OrderedItemStore,
        speak_fn: Callable[[str, str | None], None] | None = None,
        audio_device: str | None = None,
        on_queued: Callable[[TtsItem], None] | None = None,
        on_synthesized: Callable[[PcmItem], None] | None = None,
        on_play: Callable[[TtsItem], None] | None = None,
        on_done: Callable[[TtsItem], None] | None = None,
        google_cloud_project: str | None = None,
    ) -> None:
        self._queue = in_queue
        self._speak_fn = speak_fn
        self._audio_device = audio_device
        self._on_queued = on_queued
        self._on_synthesized = on_synthesized
        self._on_play = on_play
        self._on_done = on_done
        self._google_cloud_project = google_cloud_project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self._stop_event = threading.Event()
        self._synth_thread: threading.Thread | None = None
        self._play_thread: threading.Thread | None = None
        self._is_speaking = False
        self._in_flight: dict[str, TtsItem] = {}
        self._in_flight_lock = threading.Lock()
        self._lock = threading.Lock()
        self._pcm_queue: OrderedItemStore = OrderedItemStore(maxsize=3)

        if speak_fn is not None:
            logger.info("TTSPlayer using custom speak_fn (mock)")
        elif self._google_cloud_project:
            device_info = f" → {audio_device}" if audio_device else ""
            logger.info("TTSPlayer using Cloud TTS non-streaming (cmn-CN-Chirp3-HD-Sulafat%s)", device_info)
        else:
            logger.info("TTSPlayer using system TTS fallback")

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    def get_in_flight_ref(self) -> dict:
        """Return the in-flight registry (dict of items currently being synthesized).

        SessionManager passes this into tts_mutations.remove_by_id so cancellations
        can race-safely mark items that have already been get()-ed but not yet put().
        """
        return self._in_flight

    def put(self, text: str, speech_prompt: str | None, urgent: bool = False) -> TtsItem:
        """Create a TtsItem, fire on_queued, and enqueue it. Returns the item."""
        item = TtsItem.create(text, speech_prompt, urgent=urgent)
        if self._on_queued:
            self._on_queued(item)
        self._queue.put(item)
        return item

    def start(self) -> None:
        if self._speak_fn is not None:
            self._synth_thread = threading.Thread(
                target=self._run_mock, daemon=True, name="TTSSynth"
            )
            self._synth_thread.start()
        elif self._google_cloud_project:
            try:
                import sounddevice  # noqa: F401
                import numpy  # noqa: F401
            except ImportError:
                logger.warning("sounddevice/numpy not available, using fallback TTS")
                self._synth_thread = threading.Thread(
                    target=self._run_fallback, daemon=True, name="TTSSynth"
                )
                self._synth_thread.start()
                return
            self._synth_thread = threading.Thread(
                target=self._run_synth, daemon=True, name="TTSSynth"
            )
            self._play_thread = threading.Thread(
                target=self._run_play, daemon=True, name="TTSPlay"
            )
            self._synth_thread.start()
            self._play_thread.start()
        else:
            self._synth_thread = threading.Thread(
                target=self._run_fallback, daemon=True, name="TTSSynth"
            )
            self._synth_thread.start()
        logger.info("TTSPlayer started")

    def stop(self) -> None:
        self._stop_event.set()
        # Unblock synth thread
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        # Unblock play thread
        try:
            self._pcm_queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        if self._synth_thread and self._synth_thread.is_alive():
            self._synth_thread.join(timeout=8)
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=8)

    # ------------------------------------------------------------------
    # Mock path
    # ------------------------------------------------------------------

    def _run_mock(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is _SENTINEL:
                self._queue.task_done()
                break
            logger.info("[TTS MOCK] %s", item.text[:60])
            if self._on_play:
                self._on_play(item)
            with self._lock:
                self._is_speaking = True
            try:
                self._speak_fn(item.text, item.speech_prompt)
            finally:
                with self._lock:
                    self._is_speaking = False
                self._queue.task_done()
                if self._on_done:
                    self._on_done(item)
                logger.info("[TTS MOCK] Done, queue size=%d", self._queue.qsize())

    # ------------------------------------------------------------------
    # Fallback path
    # ------------------------------------------------------------------

    def _run_fallback(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is _SENTINEL:
                self._queue.task_done()
                break
            logger.info("[TTS] Speaking: %s", item.text[:60])
            if self._on_play:
                self._on_play(item)
            with self._lock:
                self._is_speaking = True
            try:
                _fallback_speak(item.text, item.speech_prompt)
            finally:
                with self._lock:
                    self._is_speaking = False
                self._queue.task_done()
                if self._on_done:
                    self._on_done(item)
                logger.info("[TTS] Done, queue size=%d", self._queue.qsize())

    # ------------------------------------------------------------------
    # Cloud TTS synthesis thread
    # ------------------------------------------------------------------

    def _run_synth(self) -> None:
        """Pull TtsItems from in_queue, synthesize to PCM, push PcmItems to pcm_queue."""
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is _SENTINEL:
                self._queue.task_done()
                self._pcm_queue.put(_SENTINEL)
                break

            # Register as in-flight so cross-container remove can find it
            with self._in_flight_lock:
                self._in_flight[item.id] = item

            logger.info("[TTS] Synthesizing: %s", item.text[:60])
            try:
                response = client.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=item.text),
                    voice=texttospeech.VoiceSelectionParams(
                        language_code="cmn-CN",
                        name="cmn-CN-Chirp3-HD-Sulafat",
                    ),
                    audio_config=texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=_SAMPLE_RATE,
                    ),
                )
            except Exception as e:
                logger.error("[TTS] Synthesis failed: %s", e)
                self._queue.task_done()
                with self._in_flight_lock:
                    self._in_flight.pop(item.id, None)
                continue

            import numpy as np
            pcm = np.frombuffer(response.audio_content, dtype=np.int16).astype(np.float32) / 32768.0
            # Fade in/out to prevent click/pop at splice boundaries caused by
            # non-zero sample values at the start/end of each TTS clip.
            if len(pcm) > _FADE_FRAMES * 2:
                fade = np.linspace(0.0, 1.0, _FADE_FRAMES, dtype=np.float32)
                pcm[:_FADE_FRAMES] *= fade
                pcm[-_FADE_FRAMES:] *= fade[::-1]
            duration = len(pcm) / _SAMPLE_RATE
            logger.info("[TTS] Synthesized %.1fs: %s", duration, item.text[:60])

            pcm_item = PcmItem(
                id=item.id,
                text=item.text,
                speech_prompt=item.speech_prompt,
                pcm=pcm,
                duration=duration,
                urgent=item.urgent,
            )
            self._queue.task_done()

            with self._in_flight_lock:
                self._in_flight.pop(item.id, None)

            if item.cancel_flag:
                logger.info("[TTS] Cancelled in-flight item %s, discarding PCM", item.id)
                continue

            self._pcm_queue.put(pcm_item)
            if self._on_synthesized:
                self._on_synthesized(pcm_item)

    # ------------------------------------------------------------------
    # Continuous playback thread
    # ------------------------------------------------------------------

    def _run_play(self) -> None:
        """Pull PcmItems from pcm_queue, write into a persistent OutputStream."""
        import numpy as np
        import sounddevice as sd

        device_idx = self._resolve_device_idx()
        silence = np.zeros(_SILENCE_FRAMES, dtype=np.float32)
        # One blocksize of silence written during idle to prevent buffer underrun.
        # Without this, the OutputStream drains when synthesis is slower than expected
        # and the hardware reports an underrun → audible pop/glitch.
        keepalive = np.zeros(960, dtype=np.float32)

        stream = sd.OutputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=device_idx,
            blocksize=960,
        )
        stream.start()

        try:
            while not self._stop_event.is_set():
                try:
                    item = self._pcm_queue.get(timeout=0.2)
                except queue.Empty:
                    stream.write(keepalive)
                    continue
                if item is _SENTINEL:
                    self._pcm_queue.task_done()
                    break

                if self._on_play:
                    self._on_play(TtsItem(id=item.id, text=item.text, speech_prompt=item.speech_prompt))
                with self._lock:
                    self._is_speaking = True

                logger.info("[TTS] Playing (%.1fs): %s", item.duration, item.text[:60])
                stream.write(item.pcm)
                stream.write(silence)  # brief gap between sentences

                with self._lock:
                    self._is_speaking = False
                self._pcm_queue.task_done()
                if self._on_done:
                    self._on_done(TtsItem(id=item.id, text=item.text, speech_prompt=item.speech_prompt))
                logger.info("[TTS] Done playing, pcm_queue size=%d", self._pcm_queue.qsize())
        finally:
            stream.stop()
            stream.close()

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
