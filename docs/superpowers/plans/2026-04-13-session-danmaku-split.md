# Session / Danmaku Split + Interrupt Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple AI session (ScriptRunner + DirectorAgent + TTSPlayer) from danmaku collection (EventCollector + Orchestrator) into two independent managers, add runtime-switchable interrupt strategy (immediate/intelligent), and update the frontend controls accordingly.

**Architecture:** New `DanmakuManager` owns EventCollector + Orchestrator; existing `SessionManager` is trimmed to AI-only. They communicate via shared `tts_queue` and `urgent_queue`. Strategy is stored on `SessionManager`, read by `DanmakuManager` via callback.

**Tech Stack:** Python 3.13, FastAPI, threading.Queue, React 19, Next.js 16 App Router, Tailwind CSS v4, shadcn CSS variable tokens.

---

## File Map

**Backend — create:**
- `src/live/danmaku_manager.py` — DanmakuManager class
- `tests/live/test_danmaku_manager.py` — tests for DanmakuManager

**Backend — modify:**
- `src/live/session.py` — strip EventCollector/Orchestrator, add strategy, add urgent_queue
- `src/live/orchestrator.py` — add urgent_queue path for intelligent strategy
- `src/live/director_agent.py` — drain urgent_queue before P2/P3 in _fire()
- `src/live/routes.py` — new /session/*, /danmaku/*, /strategy endpoints; deprecate /start /stop
- `src/api/deps.py` — add get_danmaku_manager()
- `src/api/main.py` — initialize DanmakuManager in lifespan
- `tests/live/test_session.py` — update existing tests for trimmed SessionManager
- `tests/live/test_orchestrator.py` — add urgent_queue strategy tests
- `tests/api/test_live_routes.py` — add new endpoint tests

**Frontend — modify:**
- `apps/web/src/features/live/hooks/use-live-session.ts` → rename/split to `use-ai-session.ts` + `use-danmaku-session.ts` + `use-strategy.ts`
- `apps/web/src/features/live/components/session-controls.tsx` — three rows: AI, danmaku, strategy toggle
- `apps/web/src/app/(dashboard)/live/page.tsx` — update hook imports

---

## Task 1: Trim SessionManager to AI-only + add strategy

**Files:**
- Modify: `src/live/session.py`
- Modify: `tests/live/test_session.py`

### Background

Current `SessionManager._build_and_start` creates: EventCollector, Orchestrator, ScriptRunner, TTSPlayer, DirectorAgent. We need to remove EventCollector and Orchestrator from SessionManager. We also add:
- `_strategy: Literal["immediate", "intelligent"]` field
- `_urgent_queue: queue.Queue` field (created on start, passed to DanmakuManager later)
- `get_strategy()` / `set_strategy()` public methods

The `_build_and_start` signature changes: `cdp_url` and `mock` (event-side params) are removed. `mock` remains only for the LLM mock path.

New `SessionManager.start` signature:
```python
def start(
    self,
    script_path: str,
    product_path: str,
    mock: bool,
    project: str | None,
) -> None:
```

New fields on `__init__`:
```python
self._strategy: str = "immediate"
self._urgent_queue: queue.Queue | None = None
```

New methods:
```python
def get_strategy(self) -> str:
    with self._lock:
        return self._strategy

def set_strategy(self, strategy: str) -> None:
    if strategy not in ("immediate", "intelligent"):
        raise ValueError(f"Unknown strategy: {strategy}")
    with self._lock:
        self._strategy = strategy

def get_urgent_queue(self) -> queue.Queue | None:
    with self._lock:
        return self._urgent_queue if self._running else None
```

`get_state()` adds `"strategy": self._strategy`.

- [ ] **Step 1: Write failing tests**

Add to `tests/live/test_session.py`:

```python
def test_default_strategy_is_immediate(manager):
    assert manager.get_strategy() == "immediate"

def test_set_strategy_changes_value(manager):
    manager.set_strategy("intelligent")
    assert manager.get_strategy() == "intelligent"

def test_set_invalid_strategy_raises(manager):
    with pytest.raises(ValueError):
        manager.set_strategy("unknown")

def test_get_state_includes_strategy(manager):
    state = manager.get_state()
    assert "strategy" in state

def test_urgent_queue_none_when_not_running(manager):
    assert manager.get_urgent_queue() is None
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
cd /Users/xiu/code/vision
uv run pytest tests/live/test_session.py::test_default_strategy_is_immediate tests/live/test_session.py::test_set_strategy_changes_value tests/live/test_session.py::test_set_invalid_strategy_raises tests/live/test_session.py::test_get_state_includes_strategy tests/live/test_session.py::test_urgent_queue_none_when_not_running -v
```

Expected: FAIL (AttributeError: no strategy)

- [ ] **Step 3: Add strategy fields and methods to SessionManager**

In `src/live/session.py`, update `__init__`:

```python
def __init__(self, event_bus: EventBus) -> None:
    self._bus = event_bus
    self._running = False
    self._lock = threading.Lock()
    self._components: list[Any] = []
    self._script_runner: ScriptRunner | None = None
    self._orchestrator: Orchestrator | None = None
    self._tts_queue: queue.Queue | None = None
    self._urgent_queue: queue.Queue | None = None
    self._strategy: str = "immediate"
    self._broadcaster_stop: threading.Event = threading.Event()
```

Add methods after `get_state()`:

```python
def get_strategy(self) -> str:
    with self._lock:
        return self._strategy

def set_strategy(self, strategy: str) -> None:
    if strategy not in ("immediate", "intelligent"):
        raise ValueError(f"Unknown strategy: {strategy}")
    with self._lock:
        self._strategy = strategy

def get_urgent_queue(self) -> "queue.Queue | None":
    with self._lock:
        return self._urgent_queue if self._running else None
```

Update `get_state()` to include strategy:

```python
def get_state(self) -> dict:
    with self._lock:
        running = self._running
        script_runner = self._script_runner
        tts_queue = self._tts_queue
        strategy = self._strategy
    if not running or script_runner is None:
        return {"running": False, "strategy": strategy}
    state = script_runner.get_state()
    return {
        "running": True,
        "queue_depth": tts_queue.qsize() if tts_queue else 0,
        "strategy": strategy,
        **state,
    }
```

Update `start()` signature — remove `cdp_url` parameter:

```python
def start(
    self,
    script_path: str,
    product_path: str,
    mock: bool,
    project: str | None,
) -> None:
```

Update `_build_and_start` — remove EventCollector + Orchestrator, add urgent_queue:

```python
def _build_and_start(
    self,
    script_path: str,
    product_path: str,
    mock: bool,
    project: str | None,
) -> None:
    tts_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
    urgent_queue: queue.Queue = queue.Queue(maxsize=10)
    self._tts_queue = tts_queue
    self._urgent_queue = urgent_queue

    kb = KnowledgeBase(product_path)

    if mock:
        import json as _json

        def llm_generate(prompt: str) -> str:
            return _json.dumps({
                "content": "大家好，今天给大家带来好产品！",
                "speech_prompt": "热情自然地介绍",
                "source": "script",
                "reason": "mock",
            }, ensure_ascii=False)
    else:
        if not project:
            raise ValueError("project required in production mode")
        import vertexai
        from vertexai.generative_models import GenerativeModel
        from src.live.director_agent import _SYSTEM_PROMPT
        vertexai.init(project=project, location="us-central1")
        _model = GenerativeModel(model_name="gemini-2.5-flash", system_instruction=_SYSTEM_PROMPT)

        def llm_generate(prompt: str) -> str:
            return _model.generate_content(prompt).text

    if mock:
        def speak_fn(text: str, speech_prompt: str | None = None) -> None:
            logger.info("[TTS MOCK] %s", text)
    else:
        speak_fn = None

    script_runner = ScriptRunner.from_yaml(script_path)

    def get_events_fn() -> list:
        return []  # No Orchestrator — DanmakuManager wires this separately

    tts_player = TTSPlayer(tts_queue, speak_fn=speak_fn)
    director = DirectorAgent(
        tts_queue=tts_queue,
        tts_player=tts_player,
        knowledge_ctx=kb.context_for_prompt(),
        llm_generate_fn=llm_generate,
    )

    # Wire EventBus callbacks for TTS
    original_tts_put = tts_queue.put

    def _tts_put_with_publish(item, *args, **kwargs):
        original_tts_put(item, *args, **kwargs)
        content, speech_prompt = item
        if content is _TTS_SENTINEL:
            return
        self._bus.publish({
            "type": "tts_output",
            "content": content,
            "speech_prompt": speech_prompt,
            "source": "agent",
            "ts": time.time(),
        })

    tts_queue.put = _tts_put_with_publish

    self._script_runner = script_runner

    script_runner.start()
    tts_player.start()
    director.start(
        get_state_fn=script_runner.get_state,
        get_events_fn=get_events_fn,
    )

    self._components = [script_runner, tts_player, director]

    # Script state broadcaster thread
    self._broadcaster_stop.clear()

    def _broadcast_script_state():
        while not self._broadcaster_stop.wait(timeout=5.0):
            state = script_runner.get_state()
            self._bus.publish({
                "type": "script",
                "segment_id": state.get("segment_id"),
                "remaining_seconds": state.get("remaining_seconds", 0),
                "segment_duration": state.get("segment_duration", 0),
                "finished": state.get("finished", False),
                "ts": time.time(),
            })

    broadcaster = threading.Thread(target=_broadcast_script_state, daemon=True, name="ScriptBroadcaster")
    broadcaster.start()
```

Also remove `self._orchestrator` field from `__init__` and `stop()`.

- [ ] **Step 4: Run new tests — confirm PASS**

```bash
uv run pytest tests/live/test_session.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/live/session.py tests/live/test_session.py
git commit -m "refactor(session): trim SessionManager to AI-only, add strategy and urgent_queue"
```

---

## Task 2: Update Orchestrator for urgent_queue + strategy

**Files:**
- Modify: `src/live/orchestrator.py`
- Modify: `tests/live/test_orchestrator.py`

### Background

`Orchestrator.handle_event` currently always pushes P0/P1 directly to `tts_queue`. We need it to:
- Accept a `get_strategy_fn: Callable[[], str]` in `__init__` (optional, defaults to `lambda: "immediate"`)
- Accept an `urgent_queue: queue.Queue | None` in `__init__`
- In `handle_event`, when strategy is `"intelligent"` and `urgent_queue` is not None: put the event into `urgent_queue` instead of pushing hardcoded text
- If `urgent_queue` is full (QueueFull), log a warning and drop

New `__init__`:
```python
def __init__(
    self,
    tts_queue: queue.Queue[tuple[str, str | None]],
    get_strategy_fn: Callable[[], str] | None = None,
    urgent_queue: queue.Queue | None = None,
) -> None:
    self._tts_queue = tts_queue
    self._get_strategy = get_strategy_fn or (lambda: "immediate")
    self._urgent_queue = urgent_queue
    self._buffer: list[Event] = []
    self._lock = threading.Lock()
```

New `handle_event` P0/P1 branch:
```python
if priority in ("P0", "P1"):
    strategy = self._get_strategy()
    if strategy == "intelligent" and self._urgent_queue is not None:
        try:
            self._urgent_queue.put_nowait(event)
            logger.info("[URGENT] %s queued for intelligent response", priority)
        except queue.Full:
            logger.warning("[URGENT] urgent_queue full, dropping %s event from %s", priority, event.user)
    else:
        # immediate: hardcoded template
        if priority == "P0":
            text = f"感谢{event.user}送出{event.gift}！太感谢了！"
            self._enqueue_tts(text, "收到大额礼物时真情流露的惊喜，语气先快后慢，情绪有起伏")
        else:
            text = f"欢迎{event.user}来到直播间！"
            self._enqueue_tts(text, "轻快热情地迎接新观众，像见到老朋友，语速稍快")
```

- [ ] **Step 1: Write failing tests**

Add to `tests/live/test_orchestrator.py`:

```python
import queue as _queue

def test_p0_intelligent_strategy_goes_to_urgent_queue():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue()
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "intelligent",
        urgent_queue=urgent_q,
    )
    event = Event(type="gift", user="Alice", gift="rocket", value=100, is_follower=False)
    orch.handle_event(event, {"finished": False})
    assert urgent_q.qsize() == 1
    assert tts_q.qsize() == 0

def test_p0_immediate_strategy_goes_to_tts():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue()
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "immediate",
        urgent_queue=urgent_q,
    )
    event = Event(type="gift", user="Alice", gift="rocket", value=100, is_follower=False)
    orch.handle_event(event, {"finished": False})
    assert tts_q.qsize() == 1
    assert urgent_q.qsize() == 0

def test_urgent_queue_full_drops_event():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue(maxsize=1)
    urgent_q.put("already_full")
    orch = Orchestrator(
        tts_queue=tts_q,
        get_strategy_fn=lambda: "intelligent",
        urgent_queue=urgent_q,
    )
    event = Event(type="gift", user="Bob", gift="rose", value=100, is_follower=False)
    # Should not raise, just log warning
    orch.handle_event(event, {"finished": False})
    assert urgent_q.qsize() == 1  # still 1, not 2

def test_default_strategy_is_immediate():
    tts_q = _queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)
    event = Event(type="gift", user="Alice", gift="rocket", value=100, is_follower=False)
    orch.handle_event(event, {"finished": False})
    assert tts_q.qsize() == 1
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/live/test_orchestrator.py::test_p0_intelligent_strategy_goes_to_urgent_queue tests/live/test_orchestrator.py::test_p0_immediate_strategy_goes_to_tts tests/live/test_orchestrator.py::test_urgent_queue_full_drops_event tests/live/test_orchestrator.py::test_default_strategy_is_immediate -v
```

Expected: FAIL

- [ ] **Step 3: Implement**

Replace `src/live/orchestrator.py` with:

```python
"""Orchestrator — rule-based interrupt layer (P0/P1 only).

P2/P3 events are buffered and consumed by DirectorAgent via get_events().
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from src.live.schema import Event

logger = logging.getLogger(__name__)

_QUESTION_WORDS = {"？", "?", "怎么", "如何", "为什么", "什么", "哪里", "多少", "能不能", "可以吗"}
_HIGH_VALUE_GIFT_THRESHOLD = 50   # CNY


def classify_event(event: Event) -> str:
    if event.type == "gift" and event.value >= _HIGH_VALUE_GIFT_THRESHOLD:
        return "P0"
    if event.type == "enter" and event.is_follower:
        return "P1"
    if event.type == "danmaku" and event.text and any(w in event.text for w in _QUESTION_WORDS):
        return "P2"
    return "P3"


class Orchestrator:
    def __init__(
        self,
        tts_queue: queue.Queue[tuple[str, str | None]],
        get_strategy_fn: Callable[[], str] | None = None,
        urgent_queue: queue.Queue | None = None,
    ) -> None:
        self._tts_queue = tts_queue
        self._get_strategy = get_strategy_fn or (lambda: "immediate")
        self._urgent_queue = urgent_queue
        self._buffer: list[Event] = []
        self._lock = threading.Lock()

    def handle_event(self, event: Event, script_state: dict) -> None:
        if script_state.get("finished"):
            return

        priority = classify_event(event)
        logger.info("[EVENT] %s from %s → %s", event.type, event.user, priority)

        if priority in ("P0", "P1"):
            strategy = self._get_strategy()
            if strategy == "intelligent" and self._urgent_queue is not None:
                try:
                    self._urgent_queue.put_nowait(event)
                    logger.info("[URGENT] %s from %s queued for intelligent response", priority, event.user)
                except queue.Full:
                    logger.warning("[URGENT] urgent_queue full, dropping %s event from %s", priority, event.user)
            else:
                if priority == "P0":
                    text = f"感谢{event.user}送出{event.gift}！太感谢了！"
                    self._enqueue_tts(text, "收到大额礼物时真情流露的惊喜，语气先快后慢，情绪有起伏")
                else:
                    text = f"欢迎{event.user}来到直播间！"
                    self._enqueue_tts(text, "轻快热情地迎接新观众，像见到老朋友，语速稍快")
        else:
            with self._lock:
                self._buffer.append(event)

    def get_events(self, clear: bool = True) -> list[Event]:
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
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
uv run pytest tests/live/test_orchestrator.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/live/orchestrator.py tests/live/test_orchestrator.py
git commit -m "feat(orchestrator): add urgent_queue path for intelligent interrupt strategy"
```

---

## Task 3: Update DirectorAgent to drain urgent_queue

**Files:**
- Modify: `src/live/director_agent.py`
- Modify: `tests/live/test_director_agent.py`

### Background

`DirectorAgent.__init__` receives a new optional `urgent_queue: queue.Queue | None = None`.

In `_fire()`, before calling `build_director_prompt`, drain all available items from `urgent_queue`:

```python
def _fire(self, script_state: dict, recent_events: list) -> None:
    # Drain urgent events (P0/P1 in intelligent mode)
    urgent_events: list = []
    if self._urgent_queue is not None:
        while True:
            try:
                urgent_events.append(self._urgent_queue.get_nowait())
            except queue.Empty:
                break

    all_events = urgent_events + recent_events  # urgent first
    ...
```

Update `build_director_prompt` to accept a merged event list (already the case — `recent_events` param).

New `__init__` signature:
```python
def __init__(
    self,
    tts_queue: queue.Queue,
    tts_player,
    knowledge_ctx: str,
    llm_generate_fn: Callable[[str], str],
    urgent_queue: queue.Queue | None = None,
) -> None:
    ...
    self._urgent_queue = urgent_queue
```

- [ ] **Step 1: Write failing tests**

Add to `tests/live/test_director_agent.py`:

```python
import queue as _queue

def test_director_drains_urgent_queue_before_regular_events():
    tts_q = _queue.Queue()
    urgent_q = _queue.Queue()
    spoken = []

    def fake_llm(prompt: str) -> str:
        import json
        # capture prompt to verify urgent event appears first
        spoken.append(prompt)
        return json.dumps({"content": "response", "speech_prompt": "", "source": "agent", "reason": ""})

    from src.live.tts_player import TTSPlayer
    player = TTSPlayer(tts_q, speak_fn=lambda t, sp=None: None)
    player.start()

    from src.live.director_agent import DirectorAgent
    agent = DirectorAgent(
        tts_queue=tts_q,
        tts_player=player,
        knowledge_ctx="product knowledge",
        llm_generate_fn=fake_llm,
        urgent_queue=urgent_q,
    )

    from src.live.schema import Event
    urgent_event = Event(type="gift", user="Alice", gift="rocket", value=100, is_follower=False)
    urgent_q.put(urgent_event)

    script_state = {"segment_id": "seg1", "segment_text": "intro", "remaining_seconds": 30, "finished": False, "keywords": []}
    agent._fire(script_state, [])

    import time
    time.sleep(0.2)  # let background thread finish
    player.stop()

    assert len(spoken) == 1
    assert "Alice" in spoken[0]  # urgent event user appears in prompt

def test_director_without_urgent_queue_works_normally():
    tts_q = _queue.Queue()
    spoken = []

    def fake_llm(prompt: str) -> str:
        import json
        spoken.append(prompt)
        return json.dumps({"content": "hello", "speech_prompt": "", "source": "script", "reason": ""})

    from src.live.tts_player import TTSPlayer
    player = TTSPlayer(tts_q, speak_fn=lambda t, sp=None: None)
    player.start()

    from src.live.director_agent import DirectorAgent
    agent = DirectorAgent(
        tts_queue=tts_q,
        tts_player=player,
        knowledge_ctx="ctx",
        llm_generate_fn=fake_llm,
        urgent_queue=None,
    )

    script_state = {"segment_id": "seg1", "segment_text": "text", "remaining_seconds": 30, "finished": False, "keywords": []}
    agent._fire(script_state, [])

    import time
    time.sleep(0.2)
    player.stop()
    assert len(spoken) == 1
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/live/test_director_agent.py::test_director_drains_urgent_queue_before_regular_events tests/live/test_director_agent.py::test_director_without_urgent_queue_works_normally -v
```

Expected: FAIL

- [ ] **Step 3: Implement**

In `src/live/director_agent.py`, update `__init__`:

```python
def __init__(
    self,
    tts_queue: queue.Queue,
    tts_player: Any,
    knowledge_ctx: str,
    llm_generate_fn: Callable[[str], str],
    urgent_queue: queue.Queue | None = None,
) -> None:
    self._tts_queue = tts_queue
    self._tts_player = tts_player
    self._knowledge_ctx = knowledge_ctx
    self._llm_generate = llm_generate_fn
    self._urgent_queue = urgent_queue
    self._last_said: str = ""
    self._last_fired: float = 0.0
    self._llm_in_flight: bool = False
    self._stop_event = threading.Event()
    self._thread: threading.Thread | None = None
```

Update `_fire()` to drain urgent_queue first:

```python
def _fire(self, script_state: dict, recent_events: list) -> None:
    self._llm_in_flight = True

    # Drain urgent P0/P1 events (intelligent mode)
    urgent_events: list = []
    if self._urgent_queue is not None:
        while True:
            try:
                urgent_events.append(self._urgent_queue.get_nowait())
            except queue.Empty:
                break

    all_events = urgent_events + recent_events

    def _call():
        try:
            prompt = build_director_prompt(
                script_state=script_state,
                knowledge_ctx=self._knowledge_ctx,
                recent_events=all_events,
                last_said=self._last_said,
            )
            raw = self._llm_generate(prompt)
            result = parse_director_response(raw)
            if result.content:
                self._tts_queue.put((result.content, result.speech_prompt))
                self._last_said = result.content
        except Exception as e:
            logger.error("[DIRECTOR] LLM call failed: %s", e)
        finally:
            self._llm_in_flight = False

    threading.Thread(target=_call, daemon=True, name="DirectorFire").start()
    self._last_fired = time.monotonic()
```

- [ ] **Step 4: Run all director tests**

```bash
uv run pytest tests/live/test_director_agent.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/live/director_agent.py tests/live/test_director_agent.py
git commit -m "feat(director): drain urgent_queue before regular events in intelligent mode"
```

---

## Task 4: Create DanmakuManager

**Files:**
- Create: `src/live/danmaku_manager.py`
- Create: `tests/live/test_danmaku_manager.py`

### Background

`DanmakuManager` owns EventCollector + Orchestrator. It receives:
- `event_bus: EventBus` — for publishing events to SSE
- `tts_queue: queue.Queue | None` — shared with SessionManager; may be None if AI session not running
- `get_strategy_fn: Callable[[], str]` — reads strategy from SessionManager
- `urgent_queue: queue.Queue | None` — shared with SessionManager

```python
class DanmakuManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = threading.Lock()
        self._components: list[Any] = []
        self._orchestrator: Orchestrator | None = None

    def start(
        self,
        mock: bool,
        cdp_url: str | None,
        tts_queue: queue.Queue | None,
        get_strategy_fn: Callable[[], str],
        urgent_queue: queue.Queue | None,
    ) -> None: ...

    def stop(self) -> None: ...

    def get_state(self) -> dict:
        # returns {"running": bool, "buffer_size": int}

    def get_orchestrator(self) -> Orchestrator | None: ...
```

`start()` wires event_queue with `_event_put_with_publish` callback (same pattern as current SessionManager), creates `MockEventCollector` or `CdpEventCollector`, creates `Orchestrator` with strategy/urgent_queue params.

- [ ] **Step 1: Write failing tests**

Create `tests/live/test_danmaku_manager.py`:

```python
"""Tests for DanmakuManager."""
from __future__ import annotations

import asyncio
import queue
import threading
import time

import pytest

from src.live.danmaku_manager import DanmakuManager
from src.shared.event_bus import EventBus


def make_bus():
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    return EventBus(loop)


def test_initial_state_is_stopped():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    state = mgr.get_state()
    assert state["running"] is False


def test_start_sets_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    try:
        assert mgr.get_state()["running"] is True
    finally:
        mgr.stop()


def test_start_twice_raises():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    try:
        with pytest.raises(RuntimeError):
            mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    finally:
        mgr.stop()


def test_stop_sets_not_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    mgr.stop()
    assert mgr.get_state()["running"] is False


def test_stop_when_not_running_raises():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    with pytest.raises(RuntimeError):
        mgr.stop()


def test_get_orchestrator_returns_none_when_not_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    assert mgr.get_orchestrator() is None


def test_get_orchestrator_returns_orchestrator_when_running():
    bus = make_bus()
    mgr = DanmakuManager(bus)
    tts_q = queue.Queue()
    mgr.start(mock=True, cdp_url=None, tts_queue=tts_q, get_strategy_fn=lambda: "immediate", urgent_queue=None)
    try:
        assert mgr.get_orchestrator() is not None
    finally:
        mgr.stop()
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/live/test_danmaku_manager.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement DanmakuManager**

Create `src/live/danmaku_manager.py`:

```python
"""DanmakuManager — owns EventCollector and Orchestrator."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable

from src.live.event_collector import MockEventCollector
from src.live.orchestrator import Orchestrator
from src.live.schema import Event
from src.shared.event_bus import EventBus

logger = logging.getLogger(__name__)


class DanmakuManager:
    """Manages danmaku collection and event routing independently of the AI session."""

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = threading.Lock()
        self._components: list[Any] = []
        self._orchestrator: Orchestrator | None = None

    def start(
        self,
        mock: bool,
        cdp_url: str | None,
        tts_queue: queue.Queue | None,
        get_strategy_fn: Callable[[], str],
        urgent_queue: queue.Queue | None,
    ) -> None:
        with self._lock:
            if self._running:
                raise RuntimeError("DanmakuManager already running")
            self._running = True

        try:
            self._build_and_start(mock, cdp_url, tts_queue, get_strategy_fn, urgent_queue)
        except Exception:
            with self._lock:
                self._running = False
            raise

        self._bus.publish({"type": "agent", "status": "danmaku_started", "ts": time.time()})
        logger.info("DanmakuManager: started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                raise RuntimeError("DanmakuManager not running")
            self._running = False

        for component in reversed(self._components):
            try:
                component.stop()
            except Exception as e:
                logger.warning("Error stopping component %s: %s", component, e)
        self._components.clear()
        self._orchestrator = None
        self._bus.publish({"type": "agent", "status": "danmaku_stopped", "ts": time.time()})
        logger.info("DanmakuManager: stopped")

    def get_state(self) -> dict:
        with self._lock:
            running = self._running
            orchestrator = self._orchestrator
        if not running or orchestrator is None:
            return {"running": False, "buffer_size": 0}
        return {"running": True, "buffer_size": orchestrator.buffer_size}

    def get_orchestrator(self) -> Orchestrator | None:
        with self._lock:
            return self._orchestrator if self._running else None

    def _build_and_start(
        self,
        mock: bool,
        cdp_url: str | None,
        tts_queue: queue.Queue | None,
        get_strategy_fn: Callable[[], str],
        urgent_queue: queue.Queue | None,
    ) -> None:
        event_queue: queue.Queue[Event] = queue.Queue()

        # Use a no-op queue if no TTS session running
        effective_tts_queue: queue.Queue = tts_queue if tts_queue is not None else queue.Queue()

        orchestrator = Orchestrator(
            tts_queue=effective_tts_queue,
            get_strategy_fn=get_strategy_fn,
            urgent_queue=urgent_queue,
        )

        if cdp_url:
            from src.live.cdp_collector import CdpEventCollector
            event_collector = CdpEventCollector(out_queue=event_queue, cdp_url=cdp_url)
            logger.info("DanmakuManager: using CdpEventCollector (cdp=%s)", cdp_url)
        else:
            event_collector = MockEventCollector([], event_queue)

        def _event_put_with_publish(event: Event, *args, **kwargs):
            queue.Queue.put(event_queue, event, *args, **kwargs)
            orchestrator.handle_event(event, {"finished": False})
            self._bus.publish({
                "type": event.type,
                "user": event.user,
                "text": event.text,
                "gift": event.gift,
                "value": event.value,
                "is_follower": event.is_follower,
                "ts": time.time(),
            })

        event_queue.put = _event_put_with_publish  # type: ignore[method-assign]

        self._orchestrator = orchestrator
        event_collector.start()
        self._components = [event_collector]
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
uv run pytest tests/live/test_danmaku_manager.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/live/danmaku_manager.py tests/live/test_danmaku_manager.py
git commit -m "feat(live): add DanmakuManager for independent danmaku collection"
```

---

## Task 5: Wire DanmakuManager into app + update routes

**Files:**
- Modify: `src/api/main.py`
- Modify: `src/api/deps.py`
- Modify: `src/live/routes.py`
- Modify: `tests/api/test_live_routes.py`

### Background

`main.py` lifespan adds:
```python
app.state.danmaku_manager = DanmakuManager(event_bus)
```

`deps.py` adds:
```python
def get_danmaku_manager(request: Request) -> DanmakuManager:
    return request.app.state.danmaku_manager
```

`routes.py` — new Pydantic models:

```python
class SessionStartRequest(BaseModel):
    script: str | None = None
    product: str | None = None
    mock: bool = False
    project: str | None = None

class DanmakuStartRequest(BaseModel):
    mock: bool = False
    cdp_url: str | None = None

class StrategyRequest(BaseModel):
    strategy: str  # "immediate" | "intelligent"
```

New endpoints added to `routes.py`:

```python
@router.post("/session/start")
def session_start(body: SessionStartRequest, sm: SessionManager = Depends(get_session_manager)) -> dict:
    s = get_settings()
    try:
        sm.start(
            script_path=body.script or s.default_script_path,
            product_path=body.product or s.default_product_path,
            mock=body.mock,
            project=body.project or s.google_cloud_project,
        )
    except SessionAlreadyRunningError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sm.get_state()

@router.post("/session/stop")
def session_stop(sm: SessionManager = Depends(get_session_manager)) -> dict:
    try:
        sm.stop()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sm.get_state()

@router.get("/session/state")
def session_state(sm: SessionManager = Depends(get_session_manager)) -> dict:
    return sm.get_state()

@router.post("/danmaku/start")
def danmaku_start(
    body: DanmakuStartRequest,
    sm: SessionManager = Depends(get_session_manager),
    dm: DanmakuManager = Depends(get_danmaku_manager),
) -> dict:
    s = get_settings()
    tts_queue = sm.get_tts_queue()  # None if session not running
    urgent_queue = sm.get_urgent_queue()
    try:
        dm.start(
            mock=body.mock,
            cdp_url=body.cdp_url or s.cdp_url,
            tts_queue=tts_queue,
            get_strategy_fn=sm.get_strategy,
            urgent_queue=urgent_queue,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dm.get_state()

@router.post("/danmaku/stop")
def danmaku_stop(dm: DanmakuManager = Depends(get_danmaku_manager)) -> dict:
    try:
        dm.stop()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dm.get_state()

@router.get("/danmaku/state")
def danmaku_state(dm: DanmakuManager = Depends(get_danmaku_manager)) -> dict:
    return dm.get_state()

@router.get("/strategy")
def get_strategy(sm: SessionManager = Depends(get_session_manager)) -> dict:
    return {"strategy": sm.get_strategy()}

@router.post("/strategy")
def set_strategy(body: StrategyRequest, sm: SessionManager = Depends(get_session_manager)) -> dict:
    try:
        sm.set_strategy(body.strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"strategy": sm.get_strategy()}
```

Also add `get_tts_queue()` to `SessionManager`:
```python
def get_tts_queue(self) -> "queue.Queue | None":
    with self._lock:
        return self._tts_queue if self._running else None
```

Also wire `DirectorAgent` to use `urgent_queue` from `SessionManager` — update `_build_and_start` to pass it:
```python
director = DirectorAgent(
    tts_queue=tts_queue,
    tts_player=tts_player,
    knowledge_ctx=kb.context_for_prompt(),
    llm_generate_fn=llm_generate,
    urgent_queue=urgent_queue,
)
```

- [ ] **Step 1: Write failing route tests**

Add to `tests/api/test_live_routes.py`:

```python
async def test_session_start():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/live/session/start", json={"mock": True})
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is True
    assert "strategy" in data
    # cleanup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/session/stop")

async def test_session_stop():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/session/start", json={"mock": True})
        r = await client.post("/live/session/stop")
    assert r.status_code == 200
    assert r.json()["running"] is False

async def test_session_start_twice_returns_409():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/session/start", json={"mock": True})
        r = await client.post("/live/session/start", json={"mock": True})
    assert r.status_code == 409
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/session/stop")

async def test_session_state():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/live/session/state")
    assert r.status_code == 200

async def test_danmaku_start():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/live/danmaku/start", json={"mock": True})
    assert r.status_code == 200
    assert r.json()["running"] is True
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/danmaku/stop")

async def test_danmaku_stop():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/danmaku/start", json={"mock": True})
        r = await client.post("/live/danmaku/stop")
    assert r.status_code == 200
    assert r.json()["running"] is False

async def test_danmaku_state():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/live/danmaku/state")
    assert r.status_code == 200

async def test_get_strategy():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/live/strategy")
    assert r.status_code == 200
    assert r.json()["strategy"] == "immediate"

async def test_set_strategy():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/live/strategy", json={"strategy": "intelligent"})
    assert r.status_code == 200
    assert r.json()["strategy"] == "intelligent"
    # reset
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/live/strategy", json={"strategy": "immediate"})

async def test_set_invalid_strategy_returns_400():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/live/strategy", json={"strategy": "unknown"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/api/test_live_routes.py::test_session_start tests/api/test_live_routes.py::test_get_strategy -v
```

Expected: FAIL (404 not found)

- [ ] **Step 3: Implement**

Update `src/api/main.py` lifespan to add `danmaku_manager`:

```python
from src.live.danmaku_manager import DanmakuManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    event_bus = EventBus(loop)
    db = Database("vision.db")
    await db.init()
    app.state.event_bus = event_bus
    app.state.db = db
    app.state.session_manager = SessionManager(event_bus)
    app.state.danmaku_manager = DanmakuManager(event_bus)
    yield
```

Update `src/api/deps.py`:

```python
from src.live.danmaku_manager import DanmakuManager

def get_danmaku_manager(request: Request) -> DanmakuManager:
    return request.app.state.danmaku_manager
```

Add all new endpoints to `src/live/routes.py` (as specified above). Add `get_tts_queue()` to `SessionManager`. Pass `urgent_queue` to `DirectorAgent` in `_build_and_start`.

- [ ] **Step 4: Run all route tests**

```bash
uv run pytest tests/api/test_live_routes.py -v
```

Expected: all pass

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/api/main.py src/api/deps.py src/live/routes.py src/live/session.py tests/api/test_live_routes.py
git commit -m "feat(api): add /session, /danmaku, /strategy endpoints and wire DanmakuManager"
```

---

## Task 6: Frontend — split hooks and update SessionControls

**Files:**
- Create: `apps/web/src/features/live/hooks/use-ai-session.ts`
- Create: `apps/web/src/features/live/hooks/use-danmaku-session.ts`
- Create: `apps/web/src/features/live/hooks/use-strategy.ts`
- Modify: `apps/web/src/features/live/components/session-controls.tsx`
- Modify: `apps/web/src/app/(dashboard)/live/page.tsx`
- Create: `apps/web/src/features/live/hooks/use-ai-session.test.ts` (optional, keep small)

### Background

**`use-ai-session.ts`** — polls `/live/session/state` every 5s:
```typescript
type AiSessionState = {
  running: boolean
  queue_depth?: number
  segment_id?: string
  remaining_seconds?: number
  strategy?: string
}

export function useAiSession() {
  // same pattern as old useLiveSession but hits /live/session/state
  // start() → POST /live/session/start
  // stop()  → POST /live/session/stop
  return { state, loading, error, start, stop }
}
```

**`use-danmaku-session.ts`** — polls `/live/danmaku/state` every 5s:
```typescript
type DanmakuSessionState = {
  running: boolean
  buffer_size?: number
}

export function useDanmakuSession() {
  // start() → POST /live/danmaku/start
  // stop()  → POST /live/danmaku/stop
  return { state, loading, error, start, stop }
}
```

**`use-strategy.ts`**:
```typescript
export type Strategy = 'immediate' | 'intelligent'

export function useStrategy() {
  const [strategy, setStrategyState] = useState<Strategy>('immediate')

  useEffect(() => {
    fetch(`${env.NEXT_PUBLIC_API_URL}/live/strategy`)
      .then(r => r.json())
      .then(d => setStrategyState(d.strategy))
      .catch(() => {})
  }, [])

  const setStrategy = useCallback(async (s: Strategy) => {
    const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/strategy`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ strategy: s }),
    })
    if (res.ok) {
      const data = await res.json()
      setStrategyState(data.strategy)
    }
  }, [])

  return { strategy, setStrategy }
}
```

**`session-controls.tsx`** — new props interface:
```typescript
interface Props {
  aiSession: ReturnType<typeof useAiSession>
  danmakuSession: ReturnType<typeof useDanmakuSession>
  strategy: ReturnType<typeof useStrategy>
}
```

Three rows layout:
1. **AI 主播** row: status dot + "运行中"/"已停止" + start/stop button
2. **弹幕采集** row: status dot + "采集中"/"已停止" + start/stop button
3. **插队策略** row (always visible): two buttons `及时` / `智能`, active one highlighted

**`page.tsx`** update:
```typescript
const aiSession = useAiSession()
const danmakuSession = useDanmakuSession()
const { strategy, setStrategy } = useStrategy()

// Pass to SessionControls:
<SessionControls aiSession={aiSession} danmakuSession={danmakuSession} strategy={{ strategy, setStrategy }} />

// ScriptCard uses aiSession.state.running:
<ScriptCard scriptState={scriptState} running={aiSession.state.running} />

// AiStatusCard uses aiSession.state.queue_depth:
<AiStatusCard latest={...} queueDepth={aiSession.state.queue_depth ?? 0} />
```

- [ ] **Step 1: Create use-ai-session.ts**

```typescript
'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'

type AiSessionState = {
  running: boolean
  queue_depth?: number
  segment_id?: string
  remaining_seconds?: number
  strategy?: string
}

export function useAiSession() {
  const [state, setState] = useState<AiSessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/session/state`)
      if (res.ok) setState(await res.json())
    } catch { /* backend unreachable */ }
  }, [])

  useEffect(() => {
    fetchState()
    const id = setInterval(fetchState, 5000)
    return () => clearInterval(id)
  }, [fetchState])

  const start = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/session/start`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      if (!res.ok) setError(data.detail ?? 'Failed to start')
      else setState(data)
    } catch { setError('Cannot reach backend') }
    finally { setLoading(false) }
  }, [])

  const stop = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/session/stop`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) setError(data.detail ?? 'Failed to stop')
      else setState(data)
    } catch { setError('Cannot reach backend') }
    finally { setLoading(false) }
  }, [])

  return { state, loading, error, start, stop }
}
```

- [ ] **Step 2: Create use-danmaku-session.ts**

```typescript
'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'

type DanmakuSessionState = {
  running: boolean
  buffer_size?: number
}

export function useDanmakuSession() {
  const [state, setState] = useState<DanmakuSessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/danmaku/state`)
      if (res.ok) setState(await res.json())
    } catch { /* backend unreachable */ }
  }, [])

  useEffect(() => {
    fetchState()
    const id = setInterval(fetchState, 5000)
    return () => clearInterval(id)
  }, [fetchState])

  const start = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/danmaku/start`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      if (!res.ok) setError(data.detail ?? 'Failed to start danmaku')
      else setState(data)
    } catch { setError('Cannot reach backend') }
    finally { setLoading(false) }
  }, [])

  const stop = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/danmaku/stop`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) setError(data.detail ?? 'Failed to stop danmaku')
      else setState(data)
    } catch { setError('Cannot reach backend') }
    finally { setLoading(false) }
  }, [])

  return { state, loading, error, start, stop }
}
```

- [ ] **Step 3: Create use-strategy.ts**

```typescript
'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'

export type Strategy = 'immediate' | 'intelligent'

export function useStrategy() {
  const [strategy, setStrategyState] = useState<Strategy>('immediate')

  useEffect(() => {
    fetch(`${env.NEXT_PUBLIC_API_URL}/live/strategy`)
      .then((r) => r.json())
      .then((d: { strategy: Strategy }) => setStrategyState(d.strategy))
      .catch(() => {})
  }, [])

  const setStrategy = useCallback(async (s: Strategy) => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/strategy`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ strategy: s }),
      })
      if (res.ok) {
        const data: { strategy: Strategy } = await res.json()
        setStrategyState(data.strategy)
      }
    } catch { /* ignore */ }
  }, [])

  return { strategy, setStrategy }
}
```

- [ ] **Step 4: Rewrite session-controls.tsx**

```typescript
'use client'

import { cn } from '@workspace/ui/lib/utils'
import { CircleStopIcon, RadioIcon } from 'lucide-react'

import { Button } from '@workspace/ui/components/button'

import type { useAiSession } from '../hooks/use-ai-session'
import type { useDanmakuSession } from '../hooks/use-danmaku-session'
import type { Strategy, useStrategy } from '../hooks/use-strategy'

interface Props {
  aiSession: ReturnType<typeof useAiSession>
  danmakuSession: ReturnType<typeof useDanmakuSession>
  strategy: ReturnType<typeof useStrategy>
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={cn(
      'size-2 shrink-0 rounded-full',
      active ? 'animate-pulse bg-primary' : 'bg-muted-foreground/30',
    )} />
  )
}

export function SessionControls({ aiSession, danmakuSession, strategy }: Props) {
  return (
    <div className="flex items-center gap-6">
      {/* AI session row */}
      <div className="flex items-center gap-2">
        <StatusDot active={aiSession.state.running} />
        <span className={cn('text-sm font-medium', aiSession.state.running ? 'text-foreground' : 'text-muted-foreground')}>
          AI 主播
        </span>
        {aiSession.state.running ? (
          <Button variant="destructive" size="sm" disabled={aiSession.loading} onClick={aiSession.stop}>
            <CircleStopIcon className="mr-1.5 size-3.5" />
            停止
          </Button>
        ) : (
          <Button size="sm" disabled={aiSession.loading} onClick={aiSession.start}>
            <RadioIcon className="mr-1.5 size-3.5" />
            启动
          </Button>
        )}
      </div>

      <div className="h-4 w-px bg-border" />

      {/* Danmaku row */}
      <div className="flex items-center gap-2">
        <StatusDot active={danmakuSession.state.running} />
        <span className={cn('text-sm font-medium', danmakuSession.state.running ? 'text-foreground' : 'text-muted-foreground')}>
          弹幕采集
        </span>
        {danmakuSession.state.running ? (
          <Button variant="destructive" size="sm" disabled={danmakuSession.loading} onClick={danmakuSession.stop}>
            <CircleStopIcon className="mr-1.5 size-3.5" />
            停止
          </Button>
        ) : (
          <Button size="sm" disabled={danmakuSession.loading} onClick={danmakuSession.start}>
            <RadioIcon className="mr-1.5 size-3.5" />
            开启
          </Button>
        )}
      </div>

      <div className="h-4 w-px bg-border" />

      {/* Strategy toggle */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">插队</span>
        {(['immediate', 'intelligent'] as Strategy[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => strategy.setStrategy(s)}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium transition-colors',
              strategy.strategy === s
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground',
            )}
          >
            {s === 'immediate' ? '及时' : '智能'}
          </button>
        ))}
      </div>

      {/* Errors */}
      {(aiSession.error || danmakuSession.error) && (
        <span className="text-xs text-destructive">{aiSession.error ?? danmakuSession.error}</span>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Update page.tsx**

Replace `useLiveSession` with `useAiSession` + `useDanmakuSession` + `useStrategy`:

```typescript
'use client'

import { useEffect, useState } from 'react'

import { AiOutputLog } from '@/features/live/components/ai-output-log'
import { AiStatusCard } from '@/features/live/components/ai-status-card'
import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { ScriptCard } from '@/features/live/components/script-card'
import { SessionControls } from '@/features/live/components/session-controls'
import { useAiSession } from '@/features/live/hooks/use-ai-session'
import { useDanmakuSession } from '@/features/live/hooks/use-danmaku-session'
import { useStrategy } from '@/features/live/hooks/use-strategy'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const aiSession = useAiSession()
  const danmakuSession = useDanmakuSession()
  const strategy = useStrategy()
  const { events, connected, onlineCount, aiOutputs, scriptState } = useLiveStream()

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* top bar */}
      <div className="shrink-0 border-b px-5 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold">直播控场</h1>
          <div className="flex-1">
            <SessionControls aiSession={aiSession} danmakuSession={danmakuSession} strategy={strategy} />
          </div>
        </div>
      </div>

      {/* body — client-only to avoid SSR hydration mismatch */}
      {mounted && (
        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* left col */}
          <div className="flex w-80 shrink-0 flex-col gap-3 overflow-hidden border-r p-3">
            <ScriptCard scriptState={scriptState} running={aiSession.state.running} />
          </div>

          {/* center col */}
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-3">
            <div className="shrink-0">
              <AiStatusCard
                latest={aiOutputs[aiOutputs.length - 1] ?? null}
                queueDepth={aiSession.state.queue_depth ?? 0}
              />
            </div>
            <div className="min-h-0 flex-1">
              <AiOutputLog outputs={aiOutputs} />
            </div>
          </div>

          {/* right col: danmaku feed */}
          <div className="flex w-96 shrink-0 flex-col overflow-hidden border-l p-3">
            <DanmakuFeed events={events} connected={connected} onlineCount={onlineCount} />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd apps/web && node_modules/.bin/tsc --noEmit
```

Expected: no errors

- [ ] **Step 7: Run frontend tests**

```bash
cd apps/web && npx vitest run --project unit
```

Expected: all pass (page.test.tsx mocks will need updating — update mock for `useLiveSession` → `useAiSession` + `useDanmakuSession` + `useStrategy`)

Update `apps/web/src/app/(dashboard)/live/page.test.tsx` mocks:

```typescript
vi.mock('@/features/live/hooks/use-ai-session', () => ({
  useAiSession: () => ({
    state: { running: false, queue_depth: 0 },
    loading: false, error: null, start: vi.fn(), stop: vi.fn(),
  }),
}))
vi.mock('@/features/live/hooks/use-danmaku-session', () => ({
  useDanmakuSession: () => ({
    state: { running: false, buffer_size: 0 },
    loading: false, error: null, start: vi.fn(), stop: vi.fn(),
  }),
}))
vi.mock('@/features/live/hooks/use-strategy', () => ({
  useStrategy: () => ({ strategy: 'immediate', setStrategy: vi.fn() }),
}))
// Remove old: vi.mock('@/features/live/hooks/use-live-session', ...)
```

Also update `session-controls.tsx` mock in page.test.tsx to match new props.

- [ ] **Step 8: Commit**

```bash
cd /Users/xiu/code/vision
git add apps/web/src/features/live/hooks/use-ai-session.ts \
        apps/web/src/features/live/hooks/use-danmaku-session.ts \
        apps/web/src/features/live/hooks/use-strategy.ts \
        apps/web/src/features/live/components/session-controls.tsx \
        apps/web/src/app/(dashboard)/live/page.tsx \
        apps/web/src/app/(dashboard)/live/page.test.tsx
git commit -m "feat(web): split session controls into AI/danmaku/strategy, add interrupt strategy toggle"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| SessionManager trimmed to AI-only | Task 1 |
| SessionManager.get/set_strategy | Task 1 |
| urgent_queue field on SessionManager | Task 1 |
| Orchestrator urgent_queue path for intelligent | Task 2 |
| Orchestrator get_strategy_fn callback | Task 2 |
| DirectorAgent drains urgent_queue in _fire() | Task 3 |
| DanmakuManager class | Task 4 |
| /session/start /session/stop /session/state | Task 5 |
| /danmaku/start /danmaku/stop /danmaku/state | Task 5 |
| /strategy GET + POST | Task 5 |
| useAiSession hook | Task 6 |
| useDanmakuSession hook | Task 6 |
| useStrategy hook | Task 6 |
| SessionControls three rows | Task 6 |
| page.tsx updated imports | Task 6 |

**Type consistency check:** All queue types are `queue.Queue` (untyped for flexibility). `get_strategy_fn: Callable[[], str]` used consistently in Orchestrator and DanmakuManager. `urgent_queue: queue.Queue | None` used consistently in SessionManager, Orchestrator, DirectorAgent, DanmakuManager.

**No placeholders found.**
