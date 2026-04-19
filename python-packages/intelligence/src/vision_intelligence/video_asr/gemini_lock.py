"""Process-level file lock serializing Gemini API calls where needed.

Multiple pipeline processes running concurrently can exhaust Vertex AI quota (429).
On Unix uses fcntl.flock; on Windows falls back to a no-op (single-process usage).
"""
from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

_LOCK_PATH = Path(tempfile.gettempdir()) / "vision_gemini.lock"


@contextlib.contextmanager
def gemini_lock():
    if not _HAS_FCNTL:
        yield
        return
    with open(_LOCK_PATH, "w") as fh:
        _fcntl.flock(fh, _fcntl.LOCK_EX)
        try:
            yield
        finally:
            _fcntl.flock(fh, _fcntl.LOCK_UN)
