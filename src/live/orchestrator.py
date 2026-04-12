"""Orchestrator — rule-based interrupt layer (P0/P1 only).

P2/P3 events are buffered and consumed by DirectorAgent via get_events().
The LLM decision layer has moved to DirectorAgent.
"""
from __future__ import annotations

import logging
import queue
import threading

from src.live.schema import Event

logger = logging.getLogger(__name__)

_QUESTION_WORDS = {"？", "?", "怎么", "如何", "为什么", "什么", "哪里", "多少", "能不能", "可以吗"}
_HIGH_VALUE_GIFT_THRESHOLD = 50   # CNY


def classify_event(event: Event) -> str:
    """Classify an event into a priority tier.

    Returns:
        "P0" — must respond immediately (high-value gift)
        "P1" — should greet (follower entrance)
        "P2" — question danmaku → buffer for director
        "P3" — other → buffer for director
    """
    if event.type == "gift" and event.value >= _HIGH_VALUE_GIFT_THRESHOLD:
        return "P0"
    if event.type == "enter" and event.is_follower:
        return "P1"
    if event.type == "danmaku" and event.text and any(w in event.text for w in _QUESTION_WORDS):
        return "P2"
    return "P3"


class Orchestrator:
    """P0/P1 rule interrupt layer. Buffers P2/P3 for the DirectorAgent.

    Args:
        tts_queue: Queue of (text, speech_prompt) tuples for TTSPlayer.
    """

    def __init__(self, tts_queue: queue.Queue[tuple[str, str | None]]) -> None:
        self._tts_queue = tts_queue
        self._buffer: list[Event] = []
        self._lock = threading.Lock()

    def handle_event(self, event: Event, script_state: dict) -> None:
        """Route event: P0/P1 → immediate TTS; P2/P3 → buffer."""
        if script_state.get("finished"):
            return

        priority = classify_event(event)
        logger.info("[EVENT] %s from %s → %s", event.type, event.user, priority)

        if priority == "P0":
            text = f"感谢{event.user}送出{event.gift}！太感谢了！"
            self._enqueue_tts(text, "收到大额礼物时真情流露的惊喜，语气先快后慢，情绪有起伏")
        elif priority == "P1":
            text = f"欢迎{event.user}来到直播间！"
            self._enqueue_tts(text, "轻快热情地迎接新观众，像见到老朋友，语速稍快")
        else:
            with self._lock:
                self._buffer.append(event)

    def get_events(self, clear: bool = True) -> list[Event]:
        """Return buffered P2/P3 events (consumed by DirectorAgent)."""
        with self._lock:
            events = self._buffer[:]
            if clear:
                self._buffer.clear()
            return events

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def _enqueue_tts(self, text: str, speech_prompt: str | None = None) -> None:
        self._tts_queue.put((text, speech_prompt))
        logger.info("[TTS] Interrupt queued: %s", text[:60])
