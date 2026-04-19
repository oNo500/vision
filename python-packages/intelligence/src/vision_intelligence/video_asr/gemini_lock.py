"""Process-level file lock serializing all Gemini API calls.

Multiple pipeline processes running concurrently exhaust Vertex AI quota (429).
This lock ensures only one Gemini call is in-flight at a time across all processes.
Uses fcntl.flock (POSIX) which is automatically released on process exit.
"""
from __future__ import annotations

import contextlib
import fcntl
import tempfile
from pathlib import Path

_LOCK_PATH = Path(tempfile.gettempdir()) / "vision_gemini.lock"


@contextlib.contextmanager
def gemini_lock():
    with open(_LOCK_PATH, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
