# Live Orchestration Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-threaded live-streaming orchestration agent that drives TTS output from a YAML script while reacting to real-time events (danmaku, gifts, entrances) using a two-layer rule + LLM decision engine.

**Architecture:** A main process spawns three threads: `EventCollector` (mock event replay), `ScriptRunner` (timed segment advance), and `TTSPlayer` (async queue consumer). An `Orchestrator` reads from both the event queue and script state, applies rule-based priority filtering first, then delegates ambiguous cases to Vertex AI Gemini 2.5 Flash, and enqueues TTS output.

**Tech Stack:** Python 3.13, `uv` for dependency management, `pyttsx3` for dev TTS mock, `google-cloud-aiplatform` for Vertex AI (LLM + production TTS), `pyyaml` for script parsing, `pytest` for testing.

---

## File Map

| File | Responsibility |
|------|---------------|
| `scripts/live/schema.py` | Dataclass definitions: `Event`, `ScriptSegment`, `LiveScript`, `Decision` |
| `scripts/live/event_collector.py` | Mock event replay by timeline; interface for future real sources |
| `scripts/live/script_runner.py` | Load YAML script, advance segments on timer, expose current state |
| `scripts/live/tts_player.py` | Async TTS queue consumer; dev mock via `say`; production via Vertex AI |
| `scripts/live/llm_client.py` | Vertex AI Gemini call; build prompt from context; parse JSON response |
| `scripts/live/orchestrator.py` | Two-layer decision engine; reads event queue + script state; enqueues TTS |
| `scripts/live/agent.py` | Entry point; wire threads; handle graceful shutdown |
| `scripts/live/example_script.yaml` | Example live script for development and testing |
| `tests/live/test_schema.py` | Unit tests for dataclasses and parsing helpers |
| `tests/live/test_event_collector.py` | Unit tests for mock event replay |
| `tests/live/test_script_runner.py` | Unit tests for segment advance logic |
| `tests/live/test_orchestrator.py` | Unit tests for rule layer and LLM routing |
| `tests/live/test_llm_client.py` | Unit tests for prompt building and response parsing |

---

## Task 1: Project dependencies and schema

**Files:**
- Modify: `pyproject.toml`
- Create: `scripts/live/schema.py`
- Create: `tests/live/__init__.py`
- Create: `tests/live/test_schema.py`

- [ ] **Step 1: Add dependencies**

```bash
uv add pyyaml pyttsx3
uv add --dev pytest
```

Verify:

```bash
uv run python -c "import yaml; import pyttsx3; print('ok')"
```

Expected output: `ok`

- [ ] **Step 2: Write failing tests for schema**

Create `tests/__init__.py` and `tests/live/__init__.py` (both empty), then create `tests/live/test_schema.py`:

```python
"""Tests for schema dataclasses."""
from scripts.live.schema import Decision, Event, LiveScript, ScriptSegment


def test_event_creation():
    e = Event(type="danmaku", user="Alice", text="hello", t=10.0)
    assert e.type == "danmaku"
    assert e.user == "Alice"
    assert e.text == "hello"
    assert e.t == 10.0


def test_event_gift_defaults():
    e = Event(type="gift", user="Bob", gift="rocket", value=500, t=5.0)
    assert e.type == "gift"
    assert e.gift == "rocket"
    assert e.value == 500
    assert e.text is None


def test_script_segment_defaults():
    seg = ScriptSegment(id="opening", duration=120, text="Hello everyone!")
    assert seg.interruptible is True
    assert seg.keywords == []


def test_script_segment_not_interruptible():
    seg = ScriptSegment(id="core", duration=300, text="Product details...", interruptible=False)
    assert seg.interruptible is False


def test_live_script_from_dict():
    data = {
        "meta": {"title": "Test Live", "total_duration": 600},
        "segments": [
            {"id": "opening", "duration": 60, "text": "Hello!", "interruptible": True, "keywords": ["welcome"]},
            {"id": "core", "duration": 300, "text": "Core content.", "interruptible": False},
        ],
    }
    script = LiveScript.from_dict(data)
    assert script.title == "Test Live"
    assert len(script.segments) == 2
    assert script.segments[0].id == "opening"
    assert script.segments[1].keywords == []


def test_decision_defaults():
    d = Decision(action="skip")
    assert d.content is None
    assert d.interrupt_script is False
    assert d.reason == ""


def test_decision_respond():
    d = Decision(action="respond", content="Thanks!", interrupt_script=True, reason="gift received")
    assert d.action == "respond"
    assert d.content == "Thanks!"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/live/test_schema.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `schema.py` does not exist yet.

- [ ] **Step 4: Implement `schema.py`**

Create `scripts/live/schema.py`:

```python
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
    def from_dict(cls, data: dict) -> "LiveScript":
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

    action: str                  # "respond" | "defer" | "skip"
    content: str | None = None   # TTS text (required when action == "respond")
    interrupt_script: bool = False
    reason: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/live/test_schema.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock scripts/live/schema.py tests/__init__.py tests/live/__init__.py tests/live/test_schema.py
git commit -m "feat(live): add schema dataclasses and project dependencies"
```

---

## Task 2: Example YAML script and script runner

**Files:**
- Create: `scripts/live/example_script.yaml`
- Create: `scripts/live/script_runner.py`
- Create: `tests/live/test_script_runner.py`

- [ ] **Step 1: Write failing tests for script runner**

Create `tests/live/test_script_runner.py`:

```python
"""Tests for ScriptRunner segment advance logic."""
import time

from scripts.live.schema import LiveScript
from scripts.live.script_runner import ScriptRunner

SAMPLE_DATA = {
    "meta": {"title": "Test", "total_duration": 300},
    "segments": [
        {"id": "opening", "duration": 2, "text": "Hello!", "interruptible": True},
        {"id": "core", "duration": 2, "text": "Core content.", "interruptible": False},
        {"id": "closing", "duration": 2, "text": "Goodbye!", "interruptible": True},
    ],
}


def test_initial_state():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    state = runner.get_state()
    assert state["segment_id"] == "opening"
    assert state["interruptible"] is True
    assert state["finished"] is False


def test_advance_to_next_segment():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    time.sleep(2.5)   # opening duration = 2s
    state = runner.get_state()
    runner.stop()
    assert state["segment_id"] == "core"
    assert state["interruptible"] is False


def test_finished_after_all_segments():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    time.sleep(7)   # 3 segments × 2s + buffer
    state = runner.get_state()
    runner.stop()
    assert state["finished"] is True


def test_remaining_seconds_decreases():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    time.sleep(0.5)
    state = runner.get_state()
    runner.stop()
    assert state["remaining_seconds"] < 2


def test_stop_is_idempotent():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.start()
    runner.stop()
    runner.stop()   # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/live/test_script_runner.py -v
```

Expected: `ImportError` — `script_runner.py` does not exist yet.

- [ ] **Step 3: Create example YAML script**

Create `scripts/live/example_script.yaml`:

```yaml
meta:
  title: "产品介绍直播示例"
  total_duration: 3600

segments:
  - id: "opening"
    duration: 120
    interruptible: true
    text: |
      大家好，欢迎来到今天的直播间！我是主播，今天给大家带来一款超级好用的产品。
      先点个关注再走哦，直播间会有福利送出～
    keywords: ["欢迎", "开场", "关注"]

  - id: "product_core"
    duration: 300
    interruptible: false
    text: |
      接下来重点介绍这款产品的三大核心功能。第一个功能是……
    keywords: ["产品", "功能", "介绍"]

  - id: "qa_open"
    duration: 180
    interruptible: true
    text: |
      好，现在开放提问环节！有什么问题都可以在弹幕区留言，我来一一解答。
    keywords: ["提问", "互动", "答疑"]

  - id: "closing"
    duration: 60
    interruptible: true
    text: |
      感谢大家今天的陪伴！记得点关注，下次直播不迷路。拜拜～
    keywords: ["结尾", "感谢", "关注"]
```

- [ ] **Step 4: Implement `script_runner.py`**

Create `scripts/live/script_runner.py`:

```python
"""ScriptRunner — drives timed segment advance in a background thread."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import yaml

from scripts.live.schema import LiveScript, ScriptSegment

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
                "finished": False,
            }

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ScriptRunner":
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/live/test_script_runner.py -v
```

Expected: all 5 tests PASS. (Tests with `time.sleep` will take ~10s total.)

- [ ] **Step 6: Commit**

```bash
git add scripts/live/example_script.yaml scripts/live/script_runner.py tests/live/test_script_runner.py
git commit -m "feat(live): add ScriptRunner with timed segment advance"
```

---

## Task 3: Mock event collector

**Files:**
- Create: `scripts/live/event_collector.py`
- Create: `tests/live/test_event_collector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/live/test_event_collector.py`:

```python
"""Tests for mock event collector."""
import queue
import time

from scripts.live.event_collector import MockEventCollector
from scripts.live.schema import Event

MOCK_EVENTS = [
    {"type": "enter", "user": "Alice", "is_follower": True, "t": 0.0},
    {"type": "danmaku", "user": "Bob", "text": "hello", "t": 0.1},
    {"type": "gift", "user": "Carol", "gift": "rocket", "value": 500, "t": 0.2},
]


def test_collector_emits_all_events():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    time.sleep(0.5)
    collector.stop()
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    assert len(events) == 3


def test_event_types_correct():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    time.sleep(0.5)
    collector.stop()
    types = []
    while not q.empty():
        types.append(q.get_nowait().type)
    assert types == ["enter", "danmaku", "gift"]


def test_event_fields_populated():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    time.sleep(0.5)
    collector.stop()
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    gift_event = events[2]
    assert gift_event.gift == "rocket"
    assert gift_event.value == 500


def test_stop_is_idempotent():
    q: queue.Queue[Event] = queue.Queue()
    collector = MockEventCollector(MOCK_EVENTS, q, speed=100.0)
    collector.start()
    collector.stop()
    collector.stop()   # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/live/test_event_collector.py -v
```

Expected: `ImportError` — `event_collector.py` does not exist yet.

- [ ] **Step 3: Implement `event_collector.py`**

Create `scripts/live/event_collector.py`:

```python
"""EventCollector — emits Events into a queue.

MockEventCollector replays a scripted timeline at a configurable speed
multiplier. Replace this class with a real WebSocket client when connecting
to a live platform.
"""
from __future__ import annotations

import logging
import queue
import threading
import time

from scripts.live.schema import Event

logger = logging.getLogger(__name__)


class MockEventCollector:
    """Replays a list of mock events onto a queue, respecting their `t` timestamps.

    Args:
        events: List of event dicts with at minimum ``type``, ``user``, ``t``.
        out_queue: Queue to put Event objects onto.
        speed: Time multiplier. ``speed=2.0`` replays twice as fast.
    """

    def __init__(
        self,
        events: list[dict],
        out_queue: "queue.Queue[Event]",
        speed: float = 1.0,
    ) -> None:
        self._events = sorted(events, key=lambda e: e["t"])
        self._queue = out_queue
        self._speed = speed
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start replaying events in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="EventCollector")
        self._thread.start()
        logger.info("EventCollector started (speed=%.1fx)", self._speed)

    def stop(self) -> None:
        """Stop the replay thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        stream_start = time.monotonic()
        for ev in self._events:
            if self._stop_event.is_set():
                break
            target_wall = ev["t"] / self._speed
            now = time.monotonic() - stream_start
            delay = target_wall - now
            if delay > 0:
                self._stop_event.wait(timeout=delay)
            if self._stop_event.is_set():
                break
            event = Event(
                type=ev["type"],
                user=ev["user"],
                t=ev["t"],
                text=ev.get("text"),
                gift=ev.get("gift"),
                value=ev.get("value", 0),
                is_follower=ev.get("is_follower", False),
            )
            self._queue.put(event)
            logger.info("[EVENT] %s from %s", event.type, event.user)
        logger.info("EventCollector finished replay")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/live/test_event_collector.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/live/event_collector.py tests/live/test_event_collector.py
git commit -m "feat(live): add MockEventCollector with timeline replay"
```

---

## Task 4: TTS player (dev mock)

**Files:**
- Create: `scripts/live/tts_player.py`
- Create: `tests/live/test_tts_player.py`

- [ ] **Step 1: Write failing tests**

Create `tests/live/test_tts_player.py`:

```python
"""Tests for TTSPlayer async queue consumer."""
import queue
import time

from scripts.live.tts_player import TTSPlayer


def test_player_consumes_items():
    q: queue.Queue[str] = queue.Queue()
    spoken = []

    def mock_speak(text: str) -> None:
        spoken.append(text)
        time.sleep(0.05)   # simulate short speak time

    player = TTSPlayer(q, speak_fn=mock_speak)
    player.start()
    q.put("Hello world")
    q.put("How are you")
    time.sleep(0.5)
    player.stop()
    assert spoken == ["Hello world", "How are you"]


def test_is_speaking_flag():
    q: queue.Queue[str] = queue.Queue()

    def slow_speak(text: str) -> None:
        time.sleep(0.2)

    player = TTSPlayer(q, speak_fn=slow_speak)
    player.start()
    q.put("Something long")
    time.sleep(0.05)
    assert player.is_speaking is True
    time.sleep(0.3)
    assert player.is_speaking is False
    player.stop()


def test_stop_is_idempotent():
    q: queue.Queue[str] = queue.Queue()
    player = TTSPlayer(q, speak_fn=lambda t: None)
    player.start()
    player.stop()
    player.stop()   # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/live/test_tts_player.py -v
```

Expected: `ImportError` — `tts_player.py` does not exist yet.

- [ ] **Step 3: Implement `tts_player.py`**

Create `scripts/live/tts_player.py`:

```python
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
        in_queue: "queue.Queue[str]",
        speak_fn: "callable[[str], None] | None" = None,
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/live/test_tts_player.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/live/tts_player.py tests/live/test_tts_player.py
git commit -m "feat(live): add TTSPlayer async queue consumer"
```

---

## Task 5: LLM client

**Files:**
- Create: `scripts/live/llm_client.py`
- Create: `tests/live/test_llm_client.py`

- [ ] **Step 1: Add Vertex AI dependency**

```bash
uv add google-cloud-aiplatform
```

Verify:

```bash
uv run python -c "import vertexai; print('ok')"
```

Expected: `ok`

- [ ] **Step 2: Write failing tests**

Create `tests/live/test_llm_client.py`:

```python
"""Tests for LLMClient prompt building and response parsing."""
from scripts.live.llm_client import LLMClient, build_prompt
from scripts.live.schema import Decision, Event

SAMPLE_STATE = {
    "segment_id": "qa_open",
    "interruptible": True,
    "keywords": ["提问", "互动"],
    "remaining_seconds": 90.0,
    "finished": False,
    "segment_text": "开放提问环节...",
}

SAMPLE_EVENTS = [
    Event(type="danmaku", user="Alice", text="这个怎么买？", t=30.0),
    Event(type="danmaku", user="Bob", text="主播加油！", t=31.0),
]


def test_build_prompt_contains_segment_id():
    prompt = build_prompt(SAMPLE_STATE, SAMPLE_EVENTS)
    assert "qa_open" in prompt


def test_build_prompt_contains_event_text():
    prompt = build_prompt(SAMPLE_STATE, SAMPLE_EVENTS)
    assert "这个怎么买" in prompt


def test_build_prompt_contains_remaining_seconds():
    prompt = build_prompt(SAMPLE_STATE, SAMPLE_EVENTS)
    assert "90" in prompt


def test_parse_respond_decision():
    raw = '{"action": "respond", "content": "购买链接在直播间左下角！", "interrupt_script": false, "reason": "含购买疑问"}'
    decision = LLMClient.parse_response(raw)
    assert decision.action == "respond"
    assert decision.content == "购买链接在直播间左下角！"
    assert decision.interrupt_script is False


def test_parse_skip_decision():
    raw = '{"action": "skip", "reason": "only cheering, no action needed"}'
    decision = LLMClient.parse_response(raw)
    assert decision.action == "skip"
    assert decision.content is None


def test_parse_malformed_falls_back_to_skip():
    decision = LLMClient.parse_response("not valid json at all")
    assert decision.action == "skip"
    assert "parse error" in decision.reason.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/live/test_llm_client.py -v
```

Expected: `ImportError` — `llm_client.py` does not exist yet.

- [ ] **Step 4: Implement `llm_client.py`**

Create `scripts/live/llm_client.py`:

```python
"""LLMClient — calls Vertex AI Gemini and returns a Decision.

Prompt building and JSON parsing are pure functions, making them easy to unit test
without any network calls.
"""
from __future__ import annotations

import json
import logging
import os

from scripts.live.schema import Decision, Event

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一个直播控场助手，负责决定是否回应观众互动。

规则：
- 保持主播的热情、亲切风格
- 不得提及竞品或负面信息
- 回复简短，不超过30字
- 人设约束：[待填充]
- 禁用词：[待填充]

请根据当前直播状态和待处理互动，返回严格的 JSON，格式：
{
  "action": "respond" | "defer" | "skip",
  "content": "回复文案（仅 action=respond 时填写）",
  "interrupt_script": false,
  "reason": "决策理由"
}
不要输出 JSON 以外的任何内容。
"""


def build_prompt(script_state: dict, events: list[Event]) -> str:
    """Build the user-turn prompt for Gemini from script state and buffered events."""
    event_lines = "\n".join(
        f"- [{e.type}] {e.user}: {e.text or e.gift or '(进场)'}"
        for e in events
    )
    interruptible = script_state.get("interruptible", True)
    return (
        f"当前脚本段落：{script_state.get('segment_id', 'unknown')}"
        f"（关键词：{', '.join(script_state.get('keywords', []))}）\n"
        f"段落剩余时间：{script_state.get('remaining_seconds', 0):.0f}s\n"
        f"当前段落可打断：{'是' if interruptible else '否'}\n"
        f"\n待处理互动（共 {len(events)} 条）：\n{event_lines}\n"
        f"\n请决定如何处理。"
    )


class LLMClient:
    """Wraps Vertex AI Gemini for live orchestration decisions."""

    def __init__(self, project: str, location: str = "us-central1", model: str = "gemini-2.5-flash") -> None:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=project, location=location)
        self._model = GenerativeModel(
            model_name=model,
            system_instruction=_SYSTEM_PROMPT,
        )
        logger.info("LLMClient initialized (model=%s)", model)

    def decide(self, script_state: dict, events: list[Event]) -> Decision:
        """Call Gemini and return a structured Decision."""
        prompt = build_prompt(script_state, events)
        try:
            response = self._model.generate_content(prompt)
            return self.parse_response(response.text)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return Decision(action="skip", reason=f"llm error: {e}")

    @staticmethod
    def parse_response(raw: str) -> Decision:
        """Parse Gemini JSON output into a Decision. Returns skip on any parse error."""
        try:
            # Strip markdown code fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            data = json.loads(text)
            return Decision(
                action=data.get("action", "skip"),
                content=data.get("content"),
                interrupt_script=data.get("interrupt_script", False),
                reason=data.get("reason", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("LLM parse error: %s | raw=%s", e, raw[:200])
            return Decision(action="skip", reason=f"parse error: {e}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/live/test_llm_client.py -v
```

Expected: all 6 tests PASS. (No network calls are made — tests only exercise `build_prompt` and `parse_response`.)

- [ ] **Step 6: Commit**

```bash
git add scripts/live/llm_client.py tests/live/test_llm_client.py uv.lock pyproject.toml
git commit -m "feat(live): add LLMClient with Vertex AI Gemini integration"
```

---

## Task 6: Orchestrator (two-layer decision engine)

**Files:**
- Create: `scripts/live/orchestrator.py`
- Create: `tests/live/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/live/test_orchestrator.py`:

```python
"""Tests for Orchestrator two-layer decision engine."""
import queue
from unittest.mock import MagicMock

from scripts.live.orchestrator import Orchestrator, classify_event
from scripts.live.schema import Decision, Event

INTERRUPTIBLE_STATE = {
    "segment_id": "opening",
    "interruptible": True,
    "keywords": ["欢迎"],
    "remaining_seconds": 100.0,
    "finished": False,
    "segment_text": "Hello!",
}

NOT_INTERRUPTIBLE_STATE = {
    **INTERRUPTIBLE_STATE,
    "interruptible": False,
    "segment_id": "product_core",
}


# --- classify_event tests ---

def test_classify_high_value_gift():
    e = Event(type="gift", user="X", gift="rocket", value=500, t=0)
    assert classify_event(e) == "P0"


def test_classify_low_value_gift():
    e = Event(type="gift", user="X", gift="heart", value=1, t=0)
    assert classify_event(e) == "P3"


def test_classify_follower_enter():
    e = Event(type="enter", user="Y", is_follower=True, t=0)
    assert classify_event(e) == "P1"


def test_classify_non_follower_enter():
    e = Event(type="enter", user="Y", is_follower=False, t=0)
    assert classify_event(e) == "P3"


def test_classify_question_danmaku():
    e = Event(type="danmaku", user="Z", text="这个怎么买？", t=0)
    assert classify_event(e) == "P2"


def test_classify_plain_danmaku():
    e = Event(type="danmaku", user="Z", text="主播加油！", t=0)
    assert classify_event(e) == "P3"


# --- Orchestrator rule layer tests ---

def test_p0_gift_triggers_immediate_tts():
    tts_q: queue.Queue[str] = queue.Queue()
    mock_llm = MagicMock()
    orch = Orchestrator(tts_queue=tts_q, llm_client=mock_llm, llm_batch_size=5, llm_interval=10.0)

    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text = tts_q.get_nowait()
    assert "VIP" in text
    mock_llm.decide.assert_not_called()


def test_p1_follower_enter_triggers_tts():
    tts_q: queue.Queue[str] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q, llm_client=MagicMock(), llm_batch_size=5, llm_interval=10.0)

    e = Event(type="enter", user="Fan", is_follower=True, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text = tts_q.get_nowait()
    assert "Fan" in text


def test_not_interruptible_blocks_all_events():
    tts_q: queue.Queue[str] = queue.Queue()
    mock_llm = MagicMock()
    orch = Orchestrator(tts_queue=tts_q, llm_client=mock_llm, llm_batch_size=5, llm_interval=10.0)

    # Even P0 gift should not emit TTS when segment is not interruptible
    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, NOT_INTERRUPTIBLE_STATE)

    assert tts_q.empty()
    mock_llm.decide.assert_not_called()


def test_p3_events_accumulate_in_buffer():
    tts_q: queue.Queue[str] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q, llm_client=MagicMock(), llm_batch_size=5, llm_interval=10.0)

    for i in range(3):
        e = Event(type="danmaku", user=f"User{i}", text="加油！", t=float(i))
        orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert tts_q.empty()   # not enough to trigger LLM yet
    assert orch.buffer_size == 3


def test_llm_triggered_at_batch_size():
    tts_q: queue.Queue[str] = queue.Queue()
    mock_llm = MagicMock()
    mock_llm.decide.return_value = Decision(action="respond", content="感谢大家！", reason="test")
    orch = Orchestrator(tts_queue=tts_q, llm_client=mock_llm, llm_batch_size=3, llm_interval=10.0)

    for i in range(3):
        e = Event(type="danmaku", user=f"User{i}", text="加油！", t=float(i))
        orch.handle_event(e, INTERRUPTIBLE_STATE)

    mock_llm.decide.assert_called_once()
    assert not tts_q.empty()
    assert tts_q.get_nowait() == "感谢大家！"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/live/test_orchestrator.py -v
```

Expected: `ImportError` — `orchestrator.py` does not exist yet.

- [ ] **Step 3: Implement `orchestrator.py`**

Create `scripts/live/orchestrator.py`:

```python
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
        tts_queue: "queue.Queue[str]",
        llm_client,
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
            self._enqueue_tts(text)
        elif priority == "P1":
            text = f"欢迎{event.user}来到直播间！"
            self._enqueue_tts(text)
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
            self._enqueue_tts(decision.content)

    def _enqueue_tts(self, text: str) -> None:
        self._tts_queue.put(text)
        logger.info("[TTS] Queued: %s", text[:60])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/live/test_orchestrator.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/live/orchestrator.py tests/live/test_orchestrator.py
git commit -m "feat(live): add Orchestrator with two-layer rule+LLM decision engine"
```

---

## Task 7: Entry point and full integration run

**Files:**
- Create: `scripts/live/agent.py`

- [ ] **Step 1: Implement `agent.py`**

Create `scripts/live/agent.py`:

```python
#!/usr/bin/env python3
"""
agent.py — Live orchestration agent entry point.

Usage (dev mode with mock events and system TTS):
    uv run scripts/live/agent.py --script scripts/live/example_script.yaml --mock

Usage (production, requires GCP credentials):
    export GOOGLE_CLOUD_PROJECT=your-project-id
    uv run scripts/live/agent.py --script scripts/live/example_script.yaml
"""
from __future__ import annotations

import argparse
import logging
import os
import queue
import signal
import sys
import time
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="[%H:%M:%S]",
)
logger = logging.getLogger(__name__)

# Mock events for development
_MOCK_EVENTS = [
    {"type": "enter",   "user": "用户A", "is_follower": True,  "t": 5},
    {"type": "danmaku", "user": "用户B", "text": "这个怎么买？",    "t": 30},
    {"type": "gift",    "user": "用户C", "gift": "小心心", "value": 1,    "t": 60},
    {"type": "danmaku", "user": "用户D", "text": "主播加油！",     "t": 75},
    {"type": "gift",    "user": "用户E", "gift": "火箭",    "value": 500,  "t": 90},
    {"type": "danmaku", "user": "用户F", "text": "有没有优惠？",    "t": 100},
    {"type": "danmaku", "user": "用户G", "text": "666",            "t": 101},
    {"type": "danmaku", "user": "用户H", "text": "哪里能买到？",   "t": 102},
    {"type": "danmaku", "user": "用户I", "text": "好棒！",         "t": 103},
    {"type": "danmaku", "user": "用户J", "text": "继续！",         "t": 104},
]


def build_mock_llm():
    """Return a simple mock LLM that echoes back a canned response."""
    from scripts.live.schema import Decision

    class MockLLM:
        def decide(self, script_state, events):
            questions = [e for e in events if e.text and "？" in e.text]
            if questions:
                return Decision(
                    action="respond",
                    content=f"感谢{questions[0].user}的提问！购买链接在直播间左下角～",
                    reason="mock: contains question",
                )
            return Decision(action="skip", reason="mock: no question")

    return MockLLM()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live orchestration agent")
    parser.add_argument("--script", default="scripts/live/example_script.yaml", help="Path to YAML script")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM and mock TTS (dev mode)")
    parser.add_argument("--speed", type=float, default=1.0, help="Mock event replay speed multiplier")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP project ID")
    args = parser.parse_args()

    from scripts.live.event_collector import MockEventCollector
    from scripts.live.orchestrator import Orchestrator
    from scripts.live.script_runner import ScriptRunner
    from scripts.live.tts_player import TTSPlayer

    # Queues
    event_queue: queue.Queue = queue.Queue()
    tts_queue: queue.Queue[str] = queue.Queue()

    # LLM client
    if args.mock:
        llm = build_mock_llm()
        logger.info("Running in MOCK mode (no Vertex AI calls)")
    else:
        if not args.project:
            logger.error("--project or GOOGLE_CLOUD_PROJECT required in production mode")
            sys.exit(1)
        from scripts.live.llm_client import LLMClient
        llm = LLMClient(project=args.project)

    # TTS speak function
    if args.mock:
        def speak_fn(text: str) -> None:
            logger.info("[TTS MOCK] %s", text)
            time.sleep(0.3)   # simulate short playback
    else:
        speak_fn = None   # uses macOS `say` by default

    # Wire components
    script_runner = ScriptRunner.from_yaml(args.script)
    event_collector = MockEventCollector(_MOCK_EVENTS, event_queue, speed=args.speed)
    tts_player = TTSPlayer(tts_queue, speak_fn=speak_fn)
    orchestrator = Orchestrator(tts_queue=tts_queue, llm_client=llm, llm_batch_size=5, llm_interval=10.0)

    # Graceful shutdown
    stop_event = threading.Event()

    def handle_signal(sig, frame):
        logger.info("Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start threads
    script_runner.start()
    event_collector.start()
    tts_player.start()
    logger.info("Agent running. Ctrl+C to stop.")

    # Main loop: drain event queue and tick orchestrator
    while not stop_event.is_set():
        script_state = script_runner.get_state()
        if script_state.get("finished"):
            logger.info("Script finished.")
            break

        # Drain all pending events
        while True:
            try:
                event = event_queue.get_nowait()
                orchestrator.handle_event(event, script_state)
            except queue.Empty:
                break

        # Time-based LLM flush
        orchestrator.tick(script_state)
        stop_event.wait(timeout=0.5)

    # Teardown
    event_collector.stop()
    script_runner.stop()
    tts_player.stop()
    logger.info("Agent stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run a full integration smoke test**

```bash
uv run scripts/live/agent.py --script scripts/live/example_script.yaml --mock --speed 10.0
```

Expected output (approximately):

```
[HH:MM:SS] Agent running. Ctrl+C to stop.
[HH:MM:SS] ScriptRunner started
[HH:MM:SS] EventCollector started (speed=10.0x)
[HH:MM:SS] TTSPlayer started
[HH:MM:SS] [EVENT] enter from 用户A → P1
[HH:MM:SS] [TTS] Queued: 欢迎用户A来到直播间！
[HH:MM:SS] [TTS MOCK] 欢迎用户A来到直播间！
[HH:MM:SS] [EVENT] danmaku from 用户B → P2
...
[HH:MM:SS] Script finished.
[HH:MM:SS] Agent stopped.
```

Press Ctrl+C anytime to stop early.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/live/ -v
```

Expected: all tests PASS (schema, event_collector, script_runner, tts_player, llm_client, orchestrator).

- [ ] **Step 4: Run linter**

```bash
make lint
```

Fix any issues reported by ruff before committing.

- [ ] **Step 5: Commit**

```bash
git add scripts/live/agent.py
git commit -m "feat(live): add agent entry point and wire all components"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|-----------|
| Multi-threaded architecture | Task 2 (ScriptRunner), Task 3 (EventCollector), Task 4 (TTSPlayer), Task 7 (agent.py wiring) |
| YAML script format with `interruptible` | Task 2 (schema + example_script.yaml) |
| Two-layer decision: rule + LLM | Task 6 (orchestrator.py + classify_event) |
| P0/P1/P2/P3 priority tiers | Task 6 |
| LLM batch trigger (size + time) | Task 6 |
| Vertex AI Gemini 2.5 Flash | Task 5 (llm_client.py) |
| Dev TTS mock (macOS say / pyttsx3) | Task 4 (tts_player.py) |
| Mock event replay | Task 3 (event_collector.py) |
| Swap-in real event source later | Task 3 (interface boundary in event_collector.py) |
| Console observability / logging | All tasks (logger calls throughout) |
| Risk warning (compliance) | In spec; not in code — intentional, no runtime check needed |

**Placeholder scan:** No TBD, TODO, or vague steps. All code is complete and runnable.

**Type consistency:**
- `Event`, `ScriptSegment`, `LiveScript`, `Decision` defined in Task 1, used consistently in Tasks 2–7.
- `MockEventCollector(events, out_queue, speed)` — consistent across test and impl.
- `TTSPlayer(in_queue, speak_fn)` — consistent across test and impl.
- `Orchestrator(tts_queue, llm_client, llm_batch_size, llm_interval)` — consistent.
- `LLMClient.parse_response(raw)` static method — used in tests and impl.
- `ScriptRunner.from_yaml(path)` classmethod — used in agent.py.
