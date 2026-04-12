# Director Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the reactive Orchestrator with a proactive DirectorAgent that continuously drives TTS output by reading the script, product knowledge base, and recent interactions, then using LLM to decide the next thing to say.

**Architecture:** `DirectorAgent` runs in its own background thread. It fires whenever the TTS queue is empty (and the player is idle), or at most every 15 seconds to prevent dead air. Each fire collects context (script state + knowledge summary + recent events) and calls Gemini 2.5 Flash to produce the next utterance. The existing P0/P1 rule layer is preserved as an interrupt path that bypasses the director. `KnowledgeBase` loads a YAML product file and exposes a pre-formatted context string for LLM prompts.

**Tech Stack:** Python 3.13, `uv`, `pyyaml`, `google-cloud-aiplatform` (Vertex AI), `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/live/knowledge_base.py` | **Create** | Load product YAML, expose `context_for_prompt()` string |
| `scripts/live/data/product.yaml` | **Create** | Product knowledge: intro, FAQs, selling points, banned words |
| `scripts/live/director_agent.py` | **Create** | Proactive LLM loop: reads context, enqueues next TTS line |
| `scripts/live/schema.py` | **Modify** | Add `DirectorOutput` dataclass (replaces `Decision` for director path) |
| `scripts/live/orchestrator.py` | **Modify** | Strip LLM logic; keep only P0/P1 rule interrupt layer |
| `scripts/live/agent.py` | **Modify** | Wire `KnowledgeBase` + `DirectorAgent`; remove old orchestrator LLM wiring |
| `tests/live/test_knowledge_base.py` | **Create** | Unit tests for YAML loading and context formatting |
| `tests/live/test_director_agent.py` | **Create** | Unit tests for trigger logic and LLM integration |
| `tests/live/test_orchestrator.py` | **Modify** | Remove LLM-related tests; keep P0/P1 rule tests |

---

## Task 1: Product knowledge YAML + KnowledgeBase

**Files:**
- Create: `scripts/live/data/product.yaml`
- Create: `scripts/live/knowledge_base.py`
- Create: `tests/live/test_knowledge_base.py`

- [ ] **Step 1: Write failing tests**

Create `tests/live/test_knowledge_base.py`:

```python
"""Tests for KnowledgeBase."""
import textwrap
from pathlib import Path

import pytest

from scripts.live.knowledge_base import KnowledgeBase


SAMPLE_YAML = textwrap.dedent("""\
    product:
      name: "超能面膜"
      tagline: "28天焕新肌肤"
      price: 99
      original_price: 199
      selling_points:
        - "纯植物萃取，无添加"
        - "买二送一，今天限定"
        - "明星同款，已卖出10万套"
      faqs:
        - q: "适合什么肤质？"
          a: "所有肤质均可用，敏感肌也没问题"
        - q: "怎么购买？"
          a: "点左下角购物车直接下单"
    rules:
      banned_words:
        - "最好"
        - "第一"
      must_mention_per_segment:
        product_core: ["纯植物", "买二送一"]
""")


@pytest.fixture
def kb(tmp_path):
    p = tmp_path / "product.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    return KnowledgeBase(str(p))


def test_product_name(kb):
    assert kb.product_name == "超能面膜"


def test_context_contains_selling_points(kb):
    ctx = kb.context_for_prompt()
    assert "纯植物萃取" in ctx
    assert "买二送一" in ctx


def test_context_contains_faqs(kb):
    ctx = kb.context_for_prompt()
    assert "适合什么肤质" in ctx
    assert "所有肤质均可用" in ctx


def test_banned_words(kb):
    assert "最好" in kb.banned_words
    assert "第一" in kb.banned_words


def test_must_mention(kb):
    words = kb.must_mention_for_segment("product_core")
    assert "纯植物" in words
    assert kb.must_mention_for_segment("opening") == []
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
uv run pytest tests/live/test_knowledge_base.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `knowledge_base`.

- [ ] **Step 3: Create product YAML**

Create `scripts/live/data/product.yaml`:

```yaml
product:
  name: "超能面膜"
  tagline: "28天焕新肌肤，真实可见"
  price: 99
  original_price: 199
  selling_points:
    - "纯植物萃取，无酒精无香精，敏感肌放心用"
    - "买二送一，今天直播间专属价"
    - "明星同款配方，已卖出超10万套"
    - "7天无理由退换，买了不满意直接退"
  faqs:
    - q: "适合什么肤质？"
      a: "所有肤质均可，油皮、干皮、敏感肌都测试过，不刺激"
    - q: "怎么购买？"
      a: "点左下角购物车，或者扣1我发你链接"
    - q: "效果多久见效？"
      a: "一般敷完当天就能感觉皮肤水润，持续用28天有明显改善"
    - q: "可以每天用吗？"
      a: "可以，这款是日常型面膜，每天敷15-20分钟"

rules:
  banned_words:
    - "最好"
    - "第一名"
    - "治疗"
    - "医美级"
  must_mention_per_segment:
    product_core:
      - "纯植物"
      - "买二送一"
    closing:
      - "购物车"
      - "限时"
```

- [ ] **Step 4: Implement KnowledgeBase**

Create `scripts/live/knowledge_base.py`:

```python
"""KnowledgeBase — loads product YAML and exposes a context string for LLM prompts."""
from __future__ import annotations

from pathlib import Path

import yaml


class KnowledgeBase:
    """Loads product knowledge from a YAML file.

    Args:
        path: Path to product YAML file.
    """

    def __init__(self, path: str | Path) -> None:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        self._product = data.get("product", {})
        self._rules = data.get("rules", {})

    @property
    def product_name(self) -> str:
        return self._product.get("name", "")

    @property
    def banned_words(self) -> list[str]:
        return self._rules.get("banned_words", [])

    def must_mention_for_segment(self, segment_id: str) -> list[str]:
        return self._rules.get("must_mention_per_segment", {}).get(segment_id, [])

    def context_for_prompt(self) -> str:
        """Return a compact product knowledge block for inclusion in LLM prompts."""
        p = self._product
        lines = [
            f"【产品】{p.get('name', '')} — {p.get('tagline', '')}",
            f"【价格】直播价 ¥{p.get('price', '')}（原价 ¥{p.get('original_price', '')}）",
            "【卖点】",
        ]
        for sp in p.get("selling_points", []):
            lines.append(f"  - {sp}")
        lines.append("【常见问题】")
        for faq in p.get("faqs", []):
            lines.append(f"  Q: {faq['q']}")
            lines.append(f"  A: {faq['a']}")
        return "\n".join(lines)
```

- [ ] **Step 5: Run tests to confirm PASS**

```bash
uv run pytest tests/live/test_knowledge_base.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/live/data/product.yaml scripts/live/knowledge_base.py tests/live/test_knowledge_base.py
git commit -m "feat: add KnowledgeBase with product YAML"
```

---

## Task 2: DirectorOutput schema + DirectorAgent prompt builder

**Files:**
- Modify: `scripts/live/schema.py`
- Create: `scripts/live/director_agent.py` (prompt builder only, no LLM call yet)
- Create: `tests/live/test_director_agent.py` (prompt builder tests only)

- [ ] **Step 1: Write failing tests for schema + prompt builder**

Create `tests/live/test_director_agent.py`:

```python
"""Tests for DirectorAgent."""
from scripts.live.director_agent import build_director_prompt
from scripts.live.schema import DirectorOutput, Event


SCRIPT_STATE = {
    "segment_id": "opening",
    "segment_text": "大家好，欢迎来到直播间！今天带来超能面膜。",
    "interruptible": True,
    "keywords": ["欢迎", "开场"],
    "remaining_seconds": 80.0,
    "finished": False,
    "must_say": False,
}

KNOWLEDGE_CTX = "【产品】超能面膜 — 28天焕新\n【卖点】\n  - 纯植物萃取"

EVENTS = [
    Event(type="danmaku", user="Alice", text="好期待", t=5.0),
    Event(type="gift", user="Bob", gift="小心心", value=1, t=10.0),
]


def test_build_prompt_contains_segment_text():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="")
    assert "大家好" in prompt


def test_build_prompt_contains_knowledge():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="")
    assert "超能面膜" in prompt


def test_build_prompt_contains_events():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="")
    assert "Alice" in prompt
    assert "好期待" in prompt


def test_build_prompt_contains_last_said():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="欢迎大家来到直播间")
    assert "欢迎大家来到直播间" in prompt


def test_director_output_defaults():
    out = DirectorOutput(content="你好", speech_prompt="热情")
    assert out.source == "script"
    assert out.reason == ""
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
uv run pytest tests/live/test_director_agent.py -v
```

Expected: `ImportError` for `director_agent` and `DirectorOutput`.

- [ ] **Step 3: Add DirectorOutput to schema**

In `scripts/live/schema.py`, append after the `Decision` dataclass:

```python
@dataclass
class DirectorOutput:
    """Output from the DirectorAgent LLM call."""

    content: str                      # next thing to say
    speech_prompt: str                # how to say it
    source: str = "script"            # "script" | "interaction" | "knowledge"
    reason: str = ""
```

- [ ] **Step 4: Create director_agent.py with prompt builder**

Create `scripts/live/director_agent.py`:

```python
"""DirectorAgent — proactive LLM loop that drives continuous TTS output.

The director fires whenever the TTS queue is idle, or at most every
MAX_SILENCE_SECONDS seconds. It collects full context (script state,
product knowledge, recent events) and asks Gemini to produce the next
utterance, optionally improving on the script text.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time

from scripts.live.schema import DirectorOutput, Event

logger = logging.getLogger(__name__)

MAX_SILENCE_SECONDS = 15.0   # force output if TTS has been idle this long

_SYSTEM_PROMPT = """\
你是一个经验丰富的带货主播，正在进行抖音直播。
你的任务是：根据当前直播脚本段落、产品知识和观众互动，决定下一句要说什么。

规则：
- 优先回应观众互动（问题、礼物、热情弹幕），但不能忽视脚本进度
- 改写脚本内容，让它听起来更自然、口语化，而不是照本宣科
- 如果脚本段落标记了 must_say=true，必须基于脚本原文，不可大幅偏离
- 每次只说一句话，不超过 30 字
- 禁用词不得出现在输出中
- speech_prompt 描述朗读时的情绪、语速和语气（一句话，要具体）

返回严格的 JSON，格式：
{
  "content": "下一句台词（不超过30字）",
  "speech_prompt": "朗读风格描述",
  "source": "script" | "interaction" | "knowledge",
  "reason": "决策理由（简短）"
}
不要输出 JSON 以外的任何内容。
"""


def build_director_prompt(
    script_state: dict,
    knowledge_ctx: str,
    recent_events: list[Event],
    last_said: str,
) -> str:
    """Build the user-turn prompt for the director LLM call."""
    event_lines = "\n".join(
        f"  - [{e.type}] {e.user}: {e.text or e.gift or '(进场)'}"
        for e in recent_events[-10:]   # cap at 10 most recent
    ) or "  （暂无互动）"

    must_say = script_state.get("must_say", False)
    return (
        f"=== 产品知识 ===\n{knowledge_ctx}\n\n"
        f"=== 当前脚本段落 ===\n"
        f"段落ID：{script_state.get('segment_id', 'unknown')}\n"
        f"参考原文：{script_state.get('segment_text', '').strip()}\n"
        f"关键词：{', '.join(script_state.get('keywords', []))}\n"
        f"剩余时间：{script_state.get('remaining_seconds', 0):.0f}s\n"
        f"必须贴近原文：{'是' if must_say else '否'}\n\n"
        f"=== 最近观众互动 ===\n{event_lines}\n\n"
        f"=== 上一句说的 ===\n{last_said or '（开场，还没说过话）'}\n\n"
        f"请决定下一句说什么。"
    )


def parse_director_response(raw: str) -> DirectorOutput:
    """Parse LLM JSON output into a DirectorOutput. Returns a fallback on error."""
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        data = json.loads(text)
        return DirectorOutput(
            content=data["content"],
            speech_prompt=data.get("speech_prompt", "自然平稳地说"),
            source=data.get("source", "script"),
            reason=data.get("reason", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Director parse error: %s | raw=%s", e, raw[:200])
        return DirectorOutput(content="", speech_prompt="", source="script", reason=f"parse error: {e}")
```

- [ ] **Step 5: Run tests to confirm PASS**

```bash
uv run pytest tests/live/test_director_agent.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/live/schema.py scripts/live/director_agent.py tests/live/test_director_agent.py
git commit -m "feat: add DirectorOutput schema and director prompt builder"
```

---

## Task 3: DirectorAgent thread + parse tests

**Files:**
- Modify: `scripts/live/director_agent.py` (add `DirectorAgent` class)
- Modify: `tests/live/test_director_agent.py` (add thread + parse tests)

- [ ] **Step 1: Write failing tests for parse + thread**

Append to `tests/live/test_director_agent.py`:

```python
import queue
import time
from unittest.mock import MagicMock

from scripts.live.director_agent import DirectorAgent, parse_director_response
from scripts.live.tts_player import TTSPlayer


def test_parse_valid_response():
    raw = '{"content": "欢迎大家！", "speech_prompt": "热情欢快", "source": "script", "reason": "开场"}'
    out = parse_director_response(raw)
    assert out.content == "欢迎大家！"
    assert out.speech_prompt == "热情欢快"
    assert out.source == "script"


def test_parse_malformed_returns_empty():
    out = parse_director_response("not json")
    assert out.content == ""


def test_parse_strips_markdown_fence():
    raw = '```json\n{"content": "好的", "speech_prompt": "平稳", "source": "script", "reason": ""}\n```'
    out = parse_director_response(raw)
    assert out.content == "好的"


def test_director_enqueues_content():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = False
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"content": "大家好！", "speech_prompt": "热情", "source": "script", "reason": "test"}'

    script_state = {
        "segment_id": "opening", "segment_text": "欢迎", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    }

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="【产品】测试面膜",
        llm_generate_fn=mock_llm.generate,
    )

    director._fire(script_state, recent_events=[])
    assert not tts_q.empty()
    text, prompt = tts_q.get_nowait()
    assert text == "大家好！"
    assert prompt == "热情"


def test_director_skips_when_speaking():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = True
    mock_llm = MagicMock()

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="",
        llm_generate_fn=mock_llm.generate,
    )

    script_state = {
        "segment_id": "opening", "segment_text": "", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    }
    director._fire(script_state, recent_events=[])
    mock_llm.generate.assert_not_called()
    assert tts_q.empty()


def test_director_stops_cleanly():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = False
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"content": "测试", "speech_prompt": "平稳", "source": "script", "reason": ""}'

    get_state = MagicMock(return_value={
        "segment_id": "opening", "segment_text": "测试", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    })

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="",
        llm_generate_fn=mock_llm.generate,
    )
    director.start(get_state_fn=get_state, get_events_fn=lambda: [])
    time.sleep(0.2)
    director.stop()   # must not hang
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
uv run pytest tests/live/test_director_agent.py -v
```

Expected: failures on `DirectorAgent` import.

- [ ] **Step 3: Add DirectorAgent class to director_agent.py**

Append to `scripts/live/director_agent.py` (after `parse_director_response`):

```python
class DirectorAgent:
    """Proactive TTS driver. Fires whenever TTS is idle or silence exceeds threshold.

    Args:
        tts_queue: Queue of (text, speech_prompt) tuples consumed by TTSPlayer.
        tts_player: TTSPlayer instance; used to check `is_speaking`.
        knowledge_ctx: Pre-formatted product knowledge string for LLM prompt.
        llm_generate_fn: Callable(prompt: str) -> str. Returns raw LLM JSON text.
    """

    def __init__(
        self,
        tts_queue: queue.Queue[tuple[str, str | None]],
        tts_player: object,
        knowledge_ctx: str,
        llm_generate_fn,
    ) -> None:
        self._tts_queue = tts_queue
        self._tts_player = tts_player
        self._knowledge_ctx = knowledge_ctx
        self._llm_generate = llm_generate_fn
        self._last_said = ""
        self._last_fired = 0.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, get_state_fn, get_events_fn) -> None:
        """Start the director background thread.

        Args:
            get_state_fn: Callable() -> dict (current script state snapshot).
            get_events_fn: Callable() -> list[Event] (recent buffered events).
        """
        self._thread = threading.Thread(
            target=self._run,
            args=(get_state_fn, get_events_fn),
            daemon=True,
            name="DirectorAgent",
        )
        self._thread.start()
        logger.info("DirectorAgent started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self, get_state_fn, get_events_fn) -> None:
        while not self._stop_event.is_set():
            state = get_state_fn()
            if state.get("finished"):
                break

            queue_empty = self._tts_queue.empty()
            not_speaking = not self._tts_player.is_speaking
            silence_too_long = (time.monotonic() - self._last_fired) >= MAX_SILENCE_SECONDS

            if (queue_empty and not_speaking) or silence_too_long:
                self._fire(state, get_events_fn())

            self._stop_event.wait(timeout=0.5)

    def _fire(self, script_state: dict, recent_events: list[Event]) -> None:
        """Build context and call LLM; enqueue result if non-empty."""
        if self._tts_player.is_speaking:
            return

        prompt = build_director_prompt(
            script_state, self._knowledge_ctx, recent_events, self._last_said
        )
        try:
            raw = self._llm_generate(prompt)
            output = parse_director_response(raw)
        except Exception as e:
            logger.error("Director LLM call failed: %s", e)
            return

        if not output.content:
            return

        self._tts_queue.put((output.content, output.speech_prompt))
        self._last_said = output.content
        self._last_fired = time.monotonic()
        logger.info("[DIRECTOR] %s (source=%s): %s", output.source, output.reason, output.content[:60])
```

- [ ] **Step 4: Run all director tests**

```bash
uv run pytest tests/live/test_director_agent.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/live/director_agent.py tests/live/test_director_agent.py
git commit -m "feat: add DirectorAgent proactive TTS loop"
```

---

## Task 4: Slim down Orchestrator (remove LLM layer)

**Files:**
- Modify: `scripts/live/orchestrator.py`
- Modify: `tests/live/test_orchestrator.py`

The orchestrator now only handles P0/P1 rule interrupts. P2/P3 events go into a shared buffer that `DirectorAgent` reads via `get_events_fn`.

- [ ] **Step 1: Rewrite orchestrator.py**

Replace the full content of `scripts/live/orchestrator.py` with:

```python
"""Orchestrator — rule-based interrupt layer (P0/P1 only).

P2/P3 events are buffered and consumed by DirectorAgent via get_events().
The LLM decision layer has moved to DirectorAgent.
"""
from __future__ import annotations

import logging
import queue
import threading

from scripts.live.schema import Event

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
```

- [ ] **Step 2: Update orchestrator tests**

Replace full content of `tests/live/test_orchestrator.py` with:

```python
"""Tests for Orchestrator P0/P1 rule interrupt layer."""
import queue

from scripts.live.orchestrator import Orchestrator, classify_event
from scripts.live.schema import Event

INTERRUPTIBLE_STATE = {
    "segment_id": "opening",
    "interruptible": True,
    "keywords": ["欢迎"],
    "remaining_seconds": 100.0,
    "finished": False,
    "segment_text": "Hello!",
}


# --- classify_event ---

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


# --- Orchestrator rule layer ---

def test_p0_gift_triggers_immediate_tts():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert "VIP" in text
    assert speech_prompt is not None


def test_p1_follower_enter_triggers_tts():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    e = Event(type="enter", user="Fan", is_follower=True, t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert not tts_q.empty()
    text, speech_prompt = tts_q.get_nowait()
    assert "Fan" in text
    assert speech_prompt is not None


def test_p2_p3_go_to_buffer():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    for i in range(3):
        e = Event(type="danmaku", user=f"User{i}", text="加油！", t=float(i))
        orch.handle_event(e, INTERRUPTIBLE_STATE)

    assert tts_q.empty()
    assert orch.buffer_size == 3


def test_get_events_clears_buffer():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    e = Event(type="danmaku", user="A", text="这个什么价格？", t=0)
    orch.handle_event(e, INTERRUPTIBLE_STATE)

    events = orch.get_events()
    assert len(events) == 1
    assert orch.buffer_size == 0


def test_finished_state_blocks_all():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    orch = Orchestrator(tts_queue=tts_q)

    finished = {**INTERRUPTIBLE_STATE, "finished": True}
    e = Event(type="gift", user="VIP", gift="rocket", value=500, t=0)
    orch.handle_event(e, finished)

    assert tts_q.empty()
    assert orch.buffer_size == 0
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/live/test_orchestrator.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/live/orchestrator.py tests/live/test_orchestrator.py
git commit -m "refactor: slim orchestrator to P0/P1 rule layer only, buffer P2/P3 for director"
```

---

## Task 5: Wire everything in agent.py

**Files:**
- Modify: `scripts/live/agent.py`

This task wires `KnowledgeBase`, `DirectorAgent`, and the slimmed `Orchestrator` together. No new tests needed — the integration is covered by running `--mock` mode.

- [ ] **Step 1: Replace agent.py**

Replace the full content of `scripts/live/agent.py` with:

```python
#!/usr/bin/env python3
"""
agent.py — Live orchestration agent entry point.

Usage (dev mode with mock events and mock LLM):
    uv run scripts/live/agent.py --mock

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
import threading
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="[%H:%M:%S]",
)
logger = logging.getLogger(__name__)

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

_DEFAULT_PRODUCT_YAML = "scripts/live/data/product.yaml"
_DEFAULT_SCRIPT_YAML = "scripts/live/example_script.yaml"


def _make_vertex_llm_generate_fn(project: str, location: str = "us-central1", model: str = "gemini-2.5-flash"):
    """Return a generate_fn(prompt) -> str backed by Vertex AI."""
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from scripts.live.director_agent import _SYSTEM_PROMPT

    vertexai.init(project=project, location=location)
    m = GenerativeModel(model_name=model, system_instruction=_SYSTEM_PROMPT)

    def _generate(prompt: str) -> str:
        response = m.generate_content(prompt)
        return response.text

    return _generate


def _make_mock_llm_generate_fn():
    """Return a simple mock generate_fn for dev mode."""
    import json

    def _generate(prompt: str) -> str:
        if "怎么买" in prompt or "哪里" in prompt or "优惠" in prompt:
            content = "点左下角购物车就能下单，今天直播间专属价九十九！"
            source = "interaction"
        else:
            content = "大家好，今天给大家带来一款超好用的面膜，感兴趣的扣1！"
            source = "script"
        return json.dumps({
            "content": content,
            "speech_prompt": "热情自然地介绍，语速稍快，像朋友聊天",
            "source": source,
            "reason": "mock",
        }, ensure_ascii=False)

    return _generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Live orchestration agent")
    parser.add_argument("--script", default=_DEFAULT_SCRIPT_YAML, help="Path to YAML script")
    parser.add_argument("--product", default=_DEFAULT_PRODUCT_YAML, help="Path to product knowledge YAML")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM and mock TTS (dev mode)")
    parser.add_argument("--speed", type=float, default=1.0, help="Mock event replay speed multiplier")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP project ID")
    args = parser.parse_args()

    from scripts.live.director_agent import DirectorAgent
    from scripts.live.event_collector import MockEventCollector
    from scripts.live.knowledge_base import KnowledgeBase
    from scripts.live.orchestrator import Orchestrator
    from scripts.live.script_runner import ScriptRunner
    from scripts.live.tts_player import TTSPlayer

    # Queues
    event_queue: queue.Queue = queue.Queue()
    tts_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()

    # LLM generate function
    if args.mock:
        llm_generate = _make_mock_llm_generate_fn()
        logger.info("Running in MOCK mode (no Vertex AI calls)")
    else:
        if not args.project:
            logger.error("--project or GOOGLE_CLOUD_PROJECT required in production mode")
            sys.exit(1)
        llm_generate = _make_vertex_llm_generate_fn(args.project)

    # TTS speak function
    if args.mock:
        def speak_fn(text: str, speech_prompt: str | None = None) -> None:
            logger.info("[TTS MOCK] (%s) %s", speech_prompt or "default", text)
            time.sleep(0.5)
    else:
        speak_fn = None   # uses Gemini TTS via GOOGLE_CLOUD_PROJECT env var

    # Knowledge base
    kb = KnowledgeBase(args.product)
    logger.info("KnowledgeBase loaded: %s", kb.product_name)

    # Wire components
    script_runner = ScriptRunner.from_yaml(args.script)
    event_collector = MockEventCollector(_MOCK_EVENTS, event_queue, speed=args.speed)
    tts_player = TTSPlayer(tts_queue, speak_fn=speak_fn)
    orchestrator = Orchestrator(tts_queue=tts_queue)
    director = DirectorAgent(
        tts_queue=tts_queue,
        tts_player=tts_player,
        knowledge_ctx=kb.context_for_prompt(),
        llm_generate_fn=llm_generate,
    )

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
    director.start(
        get_state_fn=script_runner.get_state,
        get_events_fn=orchestrator.get_events,
    )
    logger.info("Agent running. Ctrl+C to stop.")

    # Main loop: drain event queue into orchestrator
    while not stop_event.is_set():
        script_state = script_runner.get_state()
        if script_state.get("finished"):
            logger.info("Script finished.")
            break

        while True:
            try:
                event = event_queue.get_nowait()
                orchestrator.handle_event(event, script_state)
            except queue.Empty:
                break

        stop_event.wait(timeout=0.5)

    # Teardown
    director.stop()
    event_collector.stop()
    script_runner.stop()
    tts_player.stop()
    logger.info("Agent stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run mock mode to verify wiring**

```bash
uv run scripts/live/agent.py --mock --speed 10
```

Expected log output (within ~15s):

```
[HH:MM:SS] KnowledgeBase loaded: 超能面膜
[HH:MM:SS] DirectorAgent started
[HH:MM:SS] [DIRECTOR] script (...): 大家好，今天给大家带来一款超好用的面膜...
[HH:MM:SS] [TTS MOCK] (热情自然地介绍...) 大家好...
[HH:MM:SS] [EVENT] enter from 用户A → P1
[HH:MM:SS] [TTS] Interrupt queued: 欢迎用户A来到直播间！
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/live/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/live/agent.py
git commit -m "feat: wire DirectorAgent + KnowledgeBase into agent entry point"
```

---

## Task 6: Update README

**Files:**
- Modify: `scripts/live/README.md`

- [ ] **Step 1: Update architecture section**

Replace the architecture section in `scripts/live/README.md` with the new component list including `DirectorAgent` and `KnowledgeBase`, and update the file index table. The new flow is:

```
MockEventCollector → event_queue → Orchestrator (P0/P1 interrupt) → tts_queue → TTSPlayer
                                         ↓ buffer P2/P3
ScriptRunner (get_state) ──────────▶ DirectorAgent ──────────────→ tts_queue
KnowledgeBase (context_for_prompt) ──▶    │
                                       Gemini 2.5 Flash
```

Update the **文件索引** table to include:

| 文件 | 说明 |
|------|------|
| `director_agent.py` | 主动控场 LLM 循环，决定下一句台词 |
| `knowledge_base.py` | 加载产品 YAML，输出 LLM 上下文字符串 |
| `data/product.yaml` | 产品介绍、FAQ、禁用词、必说词 |

- [ ] **Step 2: Commit**

```bash
git add scripts/live/README.md
git commit -m "docs: update live README for director agent architecture"
```
