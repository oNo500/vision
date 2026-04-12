"""ScriptRunner — drives timed segment advance in a background thread."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import yaml

from src.live.schema import LiveScript

logger = logging.getLogger(__name__)


class ScriptRunner:
    """Loads a LiveScript and advances segments on a timer in a background thread."""

    def __init__(self, script: LiveScript) -> None:
        self._script = script
        self._index = 0
        self._segment_start = time.monotonic()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background timer thread."""
        self._segment_start = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ScriptRunner")
        self._thread.start()
        logger.info("ScriptRunner started")

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def advance(self) -> None:
        """Skip to the next segment immediately (thread-safe)."""
        with self._lock:
            if self._index < len(self._script.segments) - 1:
                self._index += 1
                self._segment_start = time.monotonic()

    def rewind(self) -> None:
        """Jump back to the previous segment (thread-safe)."""
        with self._lock:
            if self._index > 0:
                self._index -= 1
                self._segment_start = time.monotonic()

    def get_state(self) -> dict:
        """Return a snapshot of current script state (thread-safe)."""
        with self._lock:
            if self._index >= len(self._script.segments):
                return {"segment_id": None, "interruptible": False, "remaining_seconds": 0, "finished": True}
            seg = self._script.segments[self._index]
            elapsed = time.monotonic() - self._segment_start
            remaining = max(0.0, seg.duration - elapsed)
            return {
                "segment_id": seg.id,
                "segment_text": seg.text,
                "interruptible": seg.interruptible,
                "keywords": seg.keywords,
                "remaining_seconds": remaining,
                "segment_duration": seg.duration,
                "finished": False,
            }

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScriptRunner:
        """Load a LiveScript from a YAML file and return a ScriptRunner."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        script = LiveScript.from_dict(data)
        return cls(script)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if self._index >= len(self._script.segments):
                    break
                seg = self._script.segments[self._index]
                elapsed = time.monotonic() - self._segment_start

            if elapsed >= seg.duration:
                with self._lock:
                    self._index += 1
                    self._segment_start = time.monotonic()
                if self._index < len(self._script.segments):
                    next_seg = self._script.segments[self._index]
                    logger.info("[SCRIPT] → segment %s", next_seg.id)
                else:
                    logger.info("[SCRIPT] → finished")

            self._stop_event.wait(timeout=0.1)
