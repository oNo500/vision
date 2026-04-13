"""Data structures shared across all live agent modules."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserInfo:
    """Rich user metadata attached to each event."""

    uid: int = 0                    # numeric user ID
    display_id: str = ""            # custom douyin handle e.g. "douyin123"
    sec_uid: str = ""               # profile unique key
    gender: int = 0                 # 1=male 2=female 0=unknown
    is_admin: bool = False          # room moderator
    is_anchor: bool = False         # the streamer themselves
    pay_grade: int = 0              # payment grade level
    fans_club_name: str = ""        # fan club name (empty if not joined)
    fans_club_level: int = 0        # fan club level (0 if not joined)
    follow_status: int = 0          # 0=not following 1=following
    follower_count: int = 0         # number of followers


@dataclass
class Event:
    """A single live-stream interaction event."""

    type: str           # "danmaku" | "gift" | "enter" | "like" | "follow" | "fansclub" | "stats" | "end"
    user: str           # display nickname
    t: float            # seconds since stream start (used by mock replay)
    text: str | None = None         # danmaku text / fansclub content
    gift: str | None = None         # gift name
    value: int = 0                  # like count / gift diamond count / online count
    is_follower: bool = False       # whether user follows the streamer (legacy, use user_info)
    user_info: UserInfo | None = None   # rich user metadata
    # gift-specific
    gift_count: int = 0             # incremental gift count
    combo_count: int = 0            # cumulative combo count
    # enter-specific
    enter_type: int = 0             # 0=normal 6=via share
    # stats-specific
    total_pv: str = ""              # cumulative viewer count string e.g. "7.5万"
    # full proto payload — all fields, including ones not promoted above
    raw: dict | None = None


@dataclass
class ScriptSegment:
    """One timed segment of the live script."""

    id: str
    title: str           # phase name shown in UI and logs, e.g. "产品介绍"
    goal: str            # AI directive: what to do in this phase
    duration: int        # planned duration in seconds
    cue: list[str] = field(default_factory=list)   # anchor lines AI weaves in naturally
    must_say: bool = False   # True = all cue lines must be delivered verbatim
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
                title=s.get("title", f"段落{i + 1}"),
                goal=s.get("goal", s.get("text", "")),   # migrate: text -> goal
                duration=s["duration"],
                cue=s.get("cue", []),
                must_say=s.get("must_say", False),
                keywords=s.get("keywords", []),
            )
            for i, s in enumerate(data.get("segments", []))
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
