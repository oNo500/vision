"""SessionMemory — layered in-process memory for a live session.

Four layers feed the DirectorAgent prompt so generated utterances stay
coherent over a 2-hour stream:

    recent:   last N utterances verbatim   → prevents short-term repetition
    cue:      per-segment cue coverage     → prevents missing or repeating anchor lines
    topics:   full-session topic timeline  → prevents long-range selling-point repeats
    qa:       recently answered questions  → prevents duplicate answers

Queried every director tick; lookup must be <5ms, so everything is kept
in memory behind a single RLock.
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from threading import RLock


@dataclass
class TopicEntry:
    """LLM-reported topic tag with the utterance it came from."""

    tag: str
    ts: float           # monotonic seconds since session start
    utterance_id: str


@dataclass
class QAEntry:
    """A question that has already been answered."""

    question_fingerprint: str
    question_raw: str
    ts: float
    answer: str


_STOPWORDS = {"的", "了", "吗", "呢", "啊", "是", "我", "你", "这", "那", "个"}


def _fingerprint(text: str) -> str:
    """Rule-based fingerprint: sorted unique tokens joined by '|'.

    Crude but good enough for v1 — catches obvious paraphrases like
    "这个怎么吃" / "怎么吃啊" while keeping different questions distinct.
    Chinese is split per-character (no tokenizer dep), English/digits
    stay as word tokens.
    """
    lowered = text.lower()
    tokens: list[str] = []
    for ch in re.findall(r"[\u4e00-\u9fa5]", lowered):
        tokens.append(ch)
    for word in re.findall(r"[a-z0-9]+", lowered):
        tokens.append(word)
    keywords = sorted(set(tokens) - _STOPWORDS)
    return "|".join(keywords)


def _fmt_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}秒"
    if seconds < 3600:
        return f"{int(seconds / 60)}分"
    return f"{seconds / 3600:.1f}时"


class SessionMemory:
    """Layered in-process memory, thread-safe.

    Args:
        recent_window: how many recent utterances to keep verbatim.
        topic_lookback_seconds: topics newer than this render as "[近期]".
        qa_lookback_seconds: QA entries older than this are filtered from
            render and treated as not-recently-answered.
        qa_max_entries: hard cap on QA entries (FIFO eviction).
    """

    def __init__(
        self,
        recent_window: int = 20,
        topic_lookback_seconds: float = 1800.0,
        qa_lookback_seconds: float = 600.0,
        qa_max_entries: int = 50,
    ) -> None:
        self._recent: deque[str] = deque(maxlen=recent_window)
        self._cue: dict[str, set[str]] = {}
        self._topics: list[TopicEntry] = []
        self._qa: deque[QAEntry] = deque(maxlen=qa_max_entries)
        self._start_ts: float = time.monotonic()
        self._topic_lookback = topic_lookback_seconds
        self._qa_lookback = qa_lookback_seconds
        self._lock = RLock()

    # ------------------------------------------------------------------
    # write APIs
    # ------------------------------------------------------------------

    def record_utterance(
        self,
        text: str,
        topic_tag: str | None,
        utterance_id: str,
        segment_id: str | None,
        cue_hits: list[str] | None,
    ) -> None:
        """Record one director output."""
        with self._lock:
            self._recent.append(text)
            if topic_tag:
                self._topics.append(TopicEntry(
                    tag=topic_tag,
                    ts=time.monotonic() - self._start_ts,
                    utterance_id=utterance_id,
                ))
            if segment_id and cue_hits:
                self._cue.setdefault(segment_id, set()).update(cue_hits)

    def record_qa(self, question: str, answer: str) -> None:
        """Record one answered question."""
        with self._lock:
            self._qa.append(QAEntry(
                question_fingerprint=_fingerprint(question),
                question_raw=question,
                ts=time.monotonic() - self._start_ts,
                answer=answer,
            ))

    # ------------------------------------------------------------------
    # read APIs (feed build_director_prompt)
    # ------------------------------------------------------------------

    def render_recent(self) -> str:
        with self._lock:
            if not self._recent:
                return "(还没说过话)"
            return "\n".join(f"  - {t}" for t in self._recent)

    def render_topic_summary(self) -> str:
        with self._lock:
            if not self._topics:
                return "(暂无)"
            now = time.monotonic() - self._start_ts
            counts: dict[str, list[float]] = {}
            for entry in self._topics:
                counts.setdefault(entry.tag, []).append(entry.ts)

            lines = []
            for tag, ts_list in counts.items():
                last_ts = ts_list[-1]
                age = now - last_ts
                marker = "[近期]" if age < self._topic_lookback else "[较久]"
                lines.append(
                    f"  - {tag} {marker} 已讲 {len(ts_list)} 次,"
                    f"最近 {_fmt_age(age)} 前"
                )
            return "\n".join(lines)

    def render_cue_status(self, segment_id: str, all_cues: list[str]) -> str:
        with self._lock:
            if not all_cues:
                return ""
            covered = self._cue.get(segment_id, set())
            lines = [
                f"  - {cue} {'✓ 已说' if cue in covered else '✗ 未说'}"
                for cue in all_cues
            ]
            return "\n".join(lines)

    def render_recent_qa(self) -> str:
        with self._lock:
            now = time.monotonic() - self._start_ts
            recent = [q for q in self._qa if (now - q.ts) < self._qa_lookback]
            if not recent:
                return "(暂无)"
            return "\n".join(
                f"  - Q: {q.question_raw} → A: {q.answer} "
                f"({_fmt_age(now - q.ts)} 前)"
                for q in recent[-10:]
            )

    def is_question_answered(self, question: str) -> QAEntry | None:
        """Return the most recent matching QAEntry within lookback, else None."""
        fp = _fingerprint(question)
        with self._lock:
            now = time.monotonic() - self._start_ts
            for entry in reversed(self._qa):
                if (
                    entry.question_fingerprint == fp
                    and (now - entry.ts) < self._qa_lookback
                ):
                    return entry
            return None
