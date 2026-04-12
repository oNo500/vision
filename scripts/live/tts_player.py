"""TTSPlayer — async TTS queue consumer.

In development, accepts a ``speak_fn`` for easy mocking.
In production, pass ``speak_fn=None`` to use the default macOS ``say`` command.
Swap for Vertex AI Gemini-2.5-TTS when ready.
"""
from __future__ import annotations

import logging
import queue
import subprocess
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _default_speak(text: str) -> None:
    """Use macOS `say` as a zero-dependency TTS mock."""
    try:
        subprocess.run(["say", text], check=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("TTS speak failed: %s", e)


class TTSPlayer:
    """Consumes text items from a queue and speaks them one at a time.

    Args:
        in_queue: Queue of text strings to speak.
        speak_fn: Callable that blocks until speech is complete.
                  Defaults to macOS ``say``.
    """

    def __init__(
        self,
        in_queue: queue.Queue[str],
        speak_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._queue = in_queue
        self._speak = speak_fn or _default_speak
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
