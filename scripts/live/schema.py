"""Data structures shared across all live agent modules."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Event:
    """A single live-stream interaction event."""

    type: str           # "danmaku" | "gift" | "enter"
    user: str
    t: float            # seconds since stream start (used by mock replay)
    text: str | None = None    # danmaku text
    gift: str | None = None    # gift name
    value: int = 0             # gift monetary value in CNY
    is_follower: bool = False  # whether user follows the streamer


@dataclass
class ScriptSegment:
    """One timed segment of the live script."""

    id: str
    duration: int        # planned duration in seconds
    text: str            # TTS content
    interruptible: bool = True
    keywords: list[str] = field(default_factory=list)


@dataclass
class LiveScript:
    """Parsed live script."""

    title: str
    total_duration: int
    segments: list[ScriptSegment]

    @classmethod
    def from_dict(cls, data: dict) -> LiveScript:
        meta = data.get("meta", {})
        segments = [
            ScriptSegment(
                id=s["id"],
                duration=s["duration"],
                text=s["text"],
                interruptible=s.get("interruptible", True),
                keywords=s.get("keywords", []),
            )
            for s in data.get("segments", [])
        ]
        return cls(
            title=meta.get("title", ""),
            total_duration=meta.get("total_duration", 0),
            segments=segments,
        )


@dataclass
class Decision:
    """Output from the orchestrator decision engine."""

    action: str                   # "respond" | "defer" | "skip"
    content: str | None = None    # TTS text (required when action == "respond")
    speech_prompt: str | None = None  # how to speak it (tone + speed hint for TTS)
    interrupt_script: bool = False
    reason: str = ""


@dataclass
class DirectorOutput:
    """Output from the DirectorAgent LLM call."""

    content: str                      # next thing to say
    speech_prompt: str = ""           # how to say it
    source: str = "script"            # "script" | "interaction" | "knowledge"
    reason: str = ""
