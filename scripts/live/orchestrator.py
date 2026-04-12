"""Orchestrator — two-layer event decision engine.

Layer 1 (rules): fast classification by priority.
Layer 2 (LLM): handles ambiguous P2/P3 events in batches.
"""
from __future__ import annotations

import logging
import queue
import time

from scripts.live.schema import Decision, Event

logger = logging.getLogger(__name__)

_QUESTION_WORDS = {"？", "?", "怎么", "如何", "为什么", "什么", "哪里", "多少", "能不能", "可以吗"}
_HIGH_VALUE_GIFT_THRESHOLD = 50   # CNY


def classify_event(event: Event) -> str:
    """Classify an event into a priority tier.

    Returns:
        "P0" — must respond immediately (high-value gift)
        "P1" — should greet (follower entrance)
        "P2" — LLM should judge (question danmaku)
        "P3" — buffer for batch LLM processing
    """
    if event.type == "gift" and event.value >= _HIGH_VALUE_GIFT_THRESHOLD:
        return "P0"
    if event.type == "enter" and event.is_follower:
        return "P1"
    if event.type == "danmaku" and event.text and any(w in event.text for w in _QUESTION_WORDS):
        return "P2"
    return "P3"


class Orchestrator:
    """Reads events and script state; enqueues TTS text via two-layer decision.

    Args:
        tts_queue: Queue to push TTS text strings onto.
        llm_client: LLMClient instance (or mock).
        llm_batch_size: Trigger LLM when buffer reaches this size.
        llm_interval: Also trigger LLM after this many seconds if buffer non-empty.
    """

    def __init__(
        self,
        tts_queue: queue.Queue[tuple[str, str | None]],
        llm_client: object,
        llm_batch_size: int = 5,
        llm_interval: float = 10.0,
    ) -> None:
        self._tts_queue = tts_queue
        self._llm = llm_client
        self._llm_batch_size = llm_batch_size
        self._llm_interval = llm_interval
        self._buffer: list[Event] = []
        self._last_llm_call = time.monotonic()

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    def handle_event(self, event: Event, script_state: dict) -> None:
        """Process one incoming event against the current script state."""
        if script_state.get("finished"):
            return

        if not script_state.get("interruptible", True):
            # All events buffered; no TTS while segment is locked
            self._buffer.append(event)
            logger.debug("[ORCH] Segment not interruptible — buffering %s from %s", event.type, event.user)
            return

        priority = classify_event(event)
        logger.info("[EVENT] %s from %s → %s", event.type, event.user, priority)

        if priority == "P0":
            text = f"感谢{event.user}送出{event.gift}！太感谢了！"
            self._enqueue_tts(text, "收到大额礼物时真情流露的惊喜，语气先快后慢，情绪有起伏")
        elif priority == "P1":
            text = f"欢迎{event.user}来到直播间！"
            self._enqueue_tts(text, "轻快热情地迎接新观众，像见到老朋友，语速稍快")
        elif priority == "P2":
            self._buffer.append(event)
            self._maybe_call_llm(script_state)
        else:   # P3
            self._buffer.append(event)
            self._maybe_call_llm(script_state)

    def tick(self, script_state: dict) -> None:
        """Call periodically (e.g. every second) to trigger time-based LLM flush."""
        if self._buffer and not script_state.get("finished"):
            self._maybe_call_llm(script_state, force_time_check=True)

    def _maybe_call_llm(self, script_state: dict, force_time_check: bool = False) -> None:
        now = time.monotonic()
        time_triggered = force_time_check and (now - self._last_llm_call >= self._llm_interval)
        size_triggered = len(self._buffer) >= self._llm_batch_size

        if not (size_triggered or time_triggered):
            return

        events_batch = self._buffer[:]
        self._buffer.clear()
        self._last_llm_call = now

        logger.info("[LLM] Calling with %d buffered events", len(events_batch))
        decision: Decision = self._llm.decide(script_state, events_batch)
        logger.info("[LLM] action=%s reason=%s", decision.action, decision.reason)

        if decision.action == "respond" and decision.content:
            self._enqueue_tts(decision.content, decision.speech_prompt)

    def _enqueue_tts(self, text: str, speech_prompt: str | None = None) -> None:
        self._tts_queue.put((text, speech_prompt))
        logger.info("[TTS] Queued: %s", text[:60])
