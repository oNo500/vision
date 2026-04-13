# ScriptSegment Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `ScriptSegment.text` with `title` + `goal` + `cue[]` fields, giving the AI structured context and giving streamers a UI they can understand without documentation, plus drag-and-drop reordering for the segment list.

**Architecture:** Three-layer change: (1) Python backend — schema dataclass + prompt builder + session construction + plan_store normalize; (2) Frontend types + editor UI — new fields, drag-and-drop with `@atlaskit/pragmatic-drag-and-drop`; (3) Seed data updated to demonstrate the new structure. Migration is read-time normalization in `PlanStore.get()` — no DB migration needed.

**Tech Stack:** Python dataclasses, pytest-asyncio, React 19, TypeScript, `@atlaskit/pragmatic-drag-and-drop` + hitbox + react-drop-indicator, Vitest + @testing-library/react.

---

## File Map

| File | Change |
|------|--------|
| `src/live/schema.py` | Replace `ScriptSegment` fields: remove `text`+`interruptible`, add `title`+`goal`+`cue`+`must_say` |
| `src/live/director_agent.py` | Update `build_director_prompt` to use `title`, `goal`, `cue`, `must_say` from `script_state` |
| `src/live/director_agent_persona_test.py` | Update `script_state` dicts to use new fields |
| `src/live/session.py` | Update `_build_and_start` segment construction |
| `src/live/plan_store.py` | Add `_normalize_segment` helper in `get()` for backward compat |
| `src/live/plan_store_test.py` | Update `_make_plan` fixture + add normalize test |
| `apps/web/src/features/live/hooks/use-plan.ts` | Update `Segment` type |
| `apps/web/src/app/(dashboard)/live/plans/[id]/page.tsx` | Rewrite segment editor: new fields + drag-and-drop |
| `scripts/seed_plans.py` | Update sample plan to new segment structure |

---

### Task 1: Update Python `ScriptSegment` dataclass

**Files:**
- Modify: `src/live/schema.py`
- Modify: `src/live/director_agent_persona_test.py`

The current `ScriptSegment` has `text: str` and `interruptible: bool`. Replace with `title: str`, `goal: str`, `cue: list[str]`, `must_say: bool`. The `interruptible` field is removed — `must_say` replaces it semantically.

Also update `ScriptRunner.get_state()` in `src/live/script_runner.py` which currently emits `segment_text` and `interruptible` — change to emit `title`, `goal`, `cue`, `must_say`.

- [ ] **Step 1: Write failing tests for new ScriptSegment fields**

Create `src/live/schema_test.py`:

```python
"""Tests for ScriptSegment and LiveScript schema."""
from src.live.schema import ScriptSegment, LiveScript


def test_script_segment_defaults():
    seg = ScriptSegment(id="s1", title="开场", goal="欢迎观众", duration=300)
    assert seg.cue == []
    assert seg.must_say is False
    assert seg.keywords == []


def test_script_segment_with_cue():
    seg = ScriptSegment(
        id="s1",
        title="促单",
        goal="引导下单",
        duration=300,
        cue=["直播间专属价299", "库存不多了"],
        must_say=True,
        keywords=["299", "库存"],
    )
    assert seg.must_say is True
    assert len(seg.cue) == 2


def test_live_script_from_dict():
    data = {
        "meta": {"title": "测试直播", "total_duration": 600},
        "segments": [
            {
                "id": "s1",
                "title": "开场",
                "goal": "欢迎观众",
                "duration": 300,
                "cue": ["欢迎来到直播间"],
                "must_say": False,
                "keywords": ["欢迎"],
            }
        ],
    }
    script = LiveScript.from_dict(data)
    assert script.title == "测试直播"
    assert len(script.segments) == 1
    seg = script.segments[0]
    assert seg.title == "开场"
    assert seg.goal == "欢迎观众"
    assert seg.cue == ["欢迎来到直播间"]
    assert seg.must_say is False


def test_script_segment_no_text_field():
    """ScriptSegment must not have a 'text' attribute."""
    seg = ScriptSegment(id="s1", title="开场", goal="欢迎", duration=60)
    assert not hasattr(seg, "text")


def test_script_segment_no_interruptible_field():
    """ScriptSegment must not have an 'interruptible' attribute."""
    seg = ScriptSegment(id="s1", title="开场", goal="欢迎", duration=60)
    assert not hasattr(seg, "interruptible")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
source .venv/bin/activate && pytest src/live/schema_test.py -v
```

Expected: FAIL — `ScriptSegment` still has `text`, missing `title`/`goal`/`cue`/`must_say`.

- [ ] **Step 3: Update `ScriptSegment` and `LiveScript.from_dict` in `src/live/schema.py`**

Replace the `ScriptSegment` dataclass and `LiveScript.from_dict`:

```python
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
```

Update `LiveScript.from_dict`:

```python
@classmethod
def from_dict(cls, data: dict) -> LiveScript:
    meta = data.get("meta", {})
    segments = [
        ScriptSegment(
            id=s["id"],
            title=s.get("title", f"段落{i + 1}"),
            goal=s.get("goal", s.get("text", "")),   # migrate: text → goal
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
```

- [ ] **Step 4: Update `ScriptRunner.get_state()` in `src/live/script_runner.py`**

The `get_state` method currently emits `segment_text` and `interruptible`. Update it to emit the new fields:

```python
def get_state(self) -> dict:
    """Return a snapshot of current script state (thread-safe)."""
    with self._lock:
        if self._index >= len(self._script.segments):
            return {"segment_id": None, "must_say": False, "remaining_seconds": 0, "finished": True}
        seg = self._script.segments[self._index]
        elapsed = time.monotonic() - self._segment_start
        remaining = max(0.0, seg.duration - elapsed)
        return {
            "segment_id": seg.id,
            "title": seg.title,
            "goal": seg.goal,
            "cue": seg.cue,
            "must_say": seg.must_say,
            "keywords": seg.keywords,
            "remaining_seconds": remaining,
            "segment_duration": seg.duration,
            "finished": False,
        }
```

Also update the `_run` method's finished sentinel — it previously referenced `next_seg.id` only, no changes needed there.

- [ ] **Step 5: Run schema tests to confirm pass**

```bash
source .venv/bin/activate && pytest src/live/schema_test.py -v
```

Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/live/schema.py src/live/script_runner.py src/live/schema_test.py
git commit -m "feat: replace ScriptSegment.text with title+goal+cue+must_say"
```

---

### Task 2: Update `build_director_prompt` and its tests

**Files:**
- Modify: `src/live/director_agent.py`
- Modify: `src/live/director_agent_persona_test.py`

The prompt builder currently reads `segment_text`, `must_say` (bool) from `script_state`. Update it to read `title`, `goal`, `cue`, `must_say` and render the structured prompt described in the spec.

- [ ] **Step 1: Write failing tests for new prompt format**

Create `src/live/director_agent_prompt_test.py`:

```python
"""Tests for build_director_prompt with new ScriptSegment fields."""
from src.live.director_agent import build_director_prompt


def _state(must_say=False, cue=None):
    return {
        "segment_id": "s1",
        "title": "产品介绍",
        "goal": "重点讲解益生菌成分，引导观众点购物车",
        "cue": cue or ["2000亿活性益生菌", "72小时补水"],
        "must_say": must_say,
        "keywords": ["益生菌", "购物车"],
        "remaining_seconds": 600,
    }


def test_prompt_contains_title():
    prompt = build_director_prompt(_state(), "产品知识", [], "")
    assert "产品介绍" in prompt


def test_prompt_contains_goal():
    prompt = build_director_prompt(_state(), "产品知识", [], "")
    assert "重点讲解益生菌成分" in prompt


def test_prompt_contains_cue_lines():
    prompt = build_director_prompt(_state(), "产品知识", [], "")
    assert "2000亿活性益生菌" in prompt
    assert "72小时补水" in prompt


def test_prompt_must_say_false_label():
    prompt = build_director_prompt(_state(must_say=False), "产品知识", [], "")
    assert "尽量覆盖" in prompt


def test_prompt_must_say_true_label():
    prompt = build_director_prompt(_state(must_say=True), "产品知识", [], "")
    assert "必须全部逐字说出" in prompt


def test_prompt_empty_cue_no_section():
    prompt = build_director_prompt(_state(cue=[]), "产品知识", [], "")
    assert "锚点话术" not in prompt
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
source .venv/bin/activate && pytest src/live/director_agent_prompt_test.py -v
```

Expected: FAIL — prompt still uses old `segment_text` format.

- [ ] **Step 3: Update `build_director_prompt` in `src/live/director_agent.py`**

Replace the `=== 当前脚本段落 ===` section in `build_director_prompt`:

```python
def build_director_prompt(
    script_state: dict,
    knowledge_ctx: str,
    recent_events: list[Event],
    last_said: str,
    persona_ctx: str = "",
) -> str:
    """Build the user-turn prompt for the director LLM call."""
    event_lines = "\n".join(
        f"  - [{e.type}] {e.user}: {e.text or e.gift or '(进场)'}"
        for e in recent_events[-10:]
    ) or "  （暂无互动）"

    persona_section = f"=== 主播人设 ===\n{persona_ctx}\n\n" if persona_ctx else ""

    must_say = script_state.get("must_say", False)
    cue = script_state.get("cue") or []
    if cue:
        cue_label = "以下话术必须全部逐字说出" if must_say else "请在合适时机自然融入，尽量覆盖"
        cue_lines = "\n".join(f"  - {line}" for line in cue)
        cue_section = f"锚点话术（{cue_label}）：\n{cue_lines}\n"
    else:
        cue_section = ""

    return (
        f"{persona_section}"
        f"=== 产品知识 ===\n{knowledge_ctx}\n\n"
        f"=== 当前脚本段落 ===\n"
        f"阶段：{script_state.get('title', '')}\n"
        f"目标：{script_state.get('goal', '').strip()}\n"
        f"{cue_section}"
        f"关键词：{', '.join(script_state.get('keywords') or [])}\n"
        f"剩余时间：{script_state.get('remaining_seconds', 0):.0f}s\n\n"
        f"=== 最近观众互动 ===\n{event_lines}\n\n"
        f"=== 上一句说的 ===\n{last_said or '（开场，还没说过话）'}\n\n"
        f"请决定下一句说什么。"
    )
```

- [ ] **Step 4: Fix `director_agent_persona_test.py` — update script_state dicts**

The existing persona tests pass a `script_state` with `segment_text` and `must_say`. Update all three tests to use the new fields:

```python
"""Tests for persona injection in build_director_prompt."""
from src.live.director_agent import build_director_prompt


def _base_state():
    return {
        "segment_id": "s1",
        "title": "开场",
        "goal": "hello",
        "cue": [],
        "must_say": False,
        "keywords": [],
        "remaining_seconds": 30,
    }


def test_persona_ctx_appears_in_prompt():
    prompt = build_director_prompt(
        script_state=_base_state(),
        knowledge_ctx="product knowledge",
        recent_events=[],
        last_said="",
        persona_ctx="主播：小美 | 风格：热情 | 禁用词：骗子",
    )
    assert "小美" in prompt
    assert "骗子" in prompt


def test_persona_ctx_empty_does_not_break():
    prompt = build_director_prompt(
        script_state=_base_state(),
        knowledge_ctx="product knowledge",
        recent_events=[],
        last_said="",
        persona_ctx="",
    )
    assert "product knowledge" in prompt


def test_persona_ctx_default_is_empty():
    """Calling without persona_ctx should not raise."""
    prompt = build_director_prompt(
        script_state=_base_state(),
        knowledge_ctx="product knowledge",
        recent_events=[],
        last_said="",
    )
    assert isinstance(prompt, str)
```

- [ ] **Step 5: Run all director agent tests**

```bash
source .venv/bin/activate && pytest src/live/director_agent_prompt_test.py src/live/director_agent_persona_test.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/live/director_agent.py src/live/director_agent_prompt_test.py src/live/director_agent_persona_test.py
git commit -m "feat: update director prompt to use title/goal/cue structure"
```

---

### Task 3: Update `session.py` segment construction + `plan_store.py` normalize

**Files:**
- Modify: `src/live/session.py`
- Modify: `src/live/plan_store.py`
- Modify: `src/live/plan_store_test.py`
- Modify: `src/live/session_plan_test.py`

Two sub-changes:

1. `session.py` `_build_and_start` currently constructs `ScriptSegment(text=..., interruptible=...)` from plan data. Update to `ScriptSegment(title=..., goal=..., cue=..., must_say=...)`.

2. `plan_store.py` `get()` must normalize old segment data: if a segment has `text` but no `goal`, copy `text` → `goal` and set `title` = `"段落N"`.

- [ ] **Step 1: Add normalize test to `plan_store_test.py`**

Add this test at the end of `src/live/plan_store_test.py`:

```python
@pytest.mark.asyncio
async def test_get_normalizes_old_text_field(store: PlanStore):
    """Segments stored with old 'text' field are migrated on read."""
    # Insert raw old-format data bypassing create()
    plan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    old_data = json.dumps({
        "id": plan_id,
        "name": "Old Plan",
        "created_at": now,
        "updated_at": now,
        "product": {},
        "persona": {},
        "script": {
            "segments": [
                {"id": "s1", "text": "开场白", "duration": 60, "must_say": True, "keywords": ["k1"]}
            ]
        },
    })
    await store._conn.execute(
        "INSERT INTO live_plans (id, name, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (plan_id, "Old Plan", old_data, now, now),
    )
    await store._conn.commit()

    plan = await store.get(plan_id)
    seg = plan["script"]["segments"][0]
    assert seg["goal"] == "开场白"
    assert seg["title"] == "段落1"
    assert "text" not in seg
    assert seg["cue"] == []
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
source .venv/bin/activate && pytest src/live/plan_store_test.py::test_get_normalizes_old_text_field -v
```

Expected: FAIL — no normalize logic yet.

- [ ] **Step 3: Add `_normalize_segment` helper and call it in `PlanStore.get()`**

In `src/live/plan_store.py`, add the helper and update `get()`:

```python
def _normalize_segment(seg: dict, index: int) -> dict:
    """Migrate old-format segment (text field) to new format (goal/title/cue)."""
    if "text" in seg and "goal" not in seg:
        seg = {**seg, "goal": seg.pop("text"), "title": seg.get("title", f"段落{index + 1}"), "cue": seg.get("cue", [])}
    return seg


class PlanStore:
    ...
    async def get(self, plan_id: str) -> dict | None:
        """Return full plan dict or None if not found. Normalizes old segment format."""
        async with self._conn.execute(
            "SELECT data FROM live_plans WHERE id = ?", (plan_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        plan = json.loads(row[0])
        segments = plan.get("script", {}).get("segments", [])
        normalized = [_normalize_segment(s, i) for i, s in enumerate(segments)]
        plan["script"]["segments"] = normalized
        return plan
```

- [ ] **Step 4: Update `session.py` segment construction**

In `src/live/session.py`, in `_build_and_start`, replace the `ScriptSegment(...)` construction:

```python
segments=[
    ScriptSegment(
        id=s["id"],
        title=s.get("title", f"段落{i + 1}"),
        goal=s.get("goal", ""),
        duration=s["duration"],
        cue=s.get("cue", []),
        must_say=s.get("must_say", False),
        keywords=s.get("keywords", []),
    )
    for i, s in enumerate(segments_data)
],
```

- [ ] **Step 5: Update `_make_plan` fixture in `plan_store_test.py` and `session_plan_test.py`**

In `src/live/plan_store_test.py`, update `_make_plan`:

```python
def _make_plan(name: str = "Test Plan") -> dict:
    return {
        "name": name,
        "product": {"name": "P", "description": "D", "price": "99",
                    "highlights": ["h1"], "faq": [{"question": "Q", "answer": "A"}]},
        "persona": {"name": "主播", "style": "friendly",
                    "catchphrases": ["买它!"], "forbidden_words": ["违禁"]},
        "script": {"segments": [{"id": "s1", "title": "开场", "goal": "欢迎观众",
                                  "duration": 60, "cue": ["欢迎来到直播间"],
                                  "must_say": False, "keywords": ["产品"]}]},
    }
```

Read `src/live/session_plan_test.py` first to see what needs updating there, then update its plan fixture segment similarly (replace `"text"` → `"title"` + `"goal"`).

- [ ] **Step 6: Run all backend tests**

```bash
source .venv/bin/activate && pytest src/live/plan_store_test.py src/live/session_plan_test.py src/live/schema_test.py src/live/director_agent_prompt_test.py src/live/director_agent_persona_test.py -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/live/plan_store.py src/live/plan_store_test.py src/live/session.py src/live/session_plan_test.py
git commit -m "feat: normalize old segment text field in plan_store, update session construction"
```

---

### Task 4: Update frontend `Segment` type and install DnD packages

**Files:**
- Modify: `apps/web/src/features/live/hooks/use-plan.ts`

Install the three pragmatic-drag-and-drop packages and update the `Segment` TypeScript type.

- [ ] **Step 1: Install packages**

```bash
cd apps/web && pnpm add @atlaskit/pragmatic-drag-and-drop @atlaskit/pragmatic-drag-and-drop-hitbox @atlaskit/pragmatic-drag-and-drop-react-drop-indicator
```

- [ ] **Step 2: Update `Segment` type in `use-plan.ts`**

Replace:

```typescript
export type Segment = {
  id: string
  text: string
  duration: number
  must_say: boolean
  keywords: string[]
}
```

With:

```typescript
export type Segment = {
  id: string
  title: string
  goal: string
  duration: number
  cue: string[]
  must_say: boolean
  keywords: string[]
}
```

- [ ] **Step 3: Type-check**

```bash
cd apps/web && pnpm tsc --noEmit
```

Expected: errors in `page.tsx` referencing `seg.text` — that's correct, will be fixed in Task 5.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/live/hooks/use-plan.ts apps/web/package.json apps/web/pnpm-lock.yaml pnpm-lock.yaml
git commit -m "feat: update Segment type with title/goal/cue fields, install pragmatic-dnd"
```

---

### Task 5: Rewrite segment editor UI with new fields and drag-and-drop

**Files:**
- Modify: `apps/web/src/app/(dashboard)/live/plans/[id]/page.tsx`

This is the main UI task. The segment card needs new fields (title input, goal textarea, cue TagInput, must_say checkbox) and drag-and-drop reordering (replacing up/down buttons).

The DnD pattern: each segment card registers as both `draggable` (with a drag handle) and `dropTargetForElements`. The list wrapper registers `monitorForElements` to handle drops.

- [ ] **Step 1: Write tests for the updated editor**

The existing test file is at `apps/web/src/app/(dashboard)/live/plans/[id]/page.test.tsx` — check if it exists first:

```bash
ls apps/web/src/app/\(dashboard\)/live/plans/\[id\]/
```

If a test file exists, update it. If not, create `apps/web/src/app/(dashboard)/live/plans/[id]/page.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/config/env', () => ({ env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' } }))
vi.mock('next/link', () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }))

const mockPlan = {
  id: 'plan-1',
  name: '测试方案',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  product: { name: '', description: '', price: '', highlights: [], faq: [] },
  persona: { name: '', style: '', catchphrases: [], forbidden_words: [] },
  script: {
    segments: [
      { id: 's1', title: '开场', goal: '欢迎观众', duration: 300, cue: ['欢迎来到直播间'], must_say: false, keywords: [] },
      { id: 's2', title: '促单', goal: '引导下单', duration: 180, cue: ['限时优惠'], must_say: true, keywords: ['优惠'] },
    ],
  },
}

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => mockPlan })
})

describe('segment editor', () => {
  it('renders title and goal fields for each segment', async () => {
    const { default: Page } = await import('./page')
    render(<Page params={Promise.resolve({ id: 'plan-1' })} />)
    await waitFor(() => {
      expect(screen.getByDisplayValue('开场')).toBeInTheDocument()
      expect(screen.getByDisplayValue('欢迎观众')).toBeInTheDocument()
    })
  })

  it('renders must_say checkbox checked for must_say segment', async () => {
    const { default: Page } = await import('./page')
    render(<Page params={Promise.resolve({ id: 'plan-1' })} />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      // s2 has must_say=true, s1 has must_say=false
      expect(checkboxes.some((cb) => (cb as HTMLInputElement).checked)).toBe(true)
    })
  })

  it('does not render up/down move buttons', async () => {
    const { default: Page } = await import('./page')
    render(<Page params={Promise.resolve({ id: 'plan-1' })} />)
    await waitFor(() => {
      expect(screen.queryByText('up')).not.toBeInTheDocument()
      expect(screen.queryByText('down')).not.toBeInTheDocument()
    })
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd apps/web && pnpm test --run -- src/app/\(dashboard\)/live/plans/\[id\]
```

Expected: FAIL — `seg.text` type error or rendering old fields.

- [ ] **Step 3: Rewrite the script tab section in `page.tsx`**

In `apps/web/src/app/(dashboard)/live/plans/[id]/page.tsx`:

1. Add imports at the top:

```tsx
import { useEffect, useRef, useState } from 'react'
import { combine } from '@atlaskit/pragmatic-drag-and-drop/combine'
import { draggable, dropTargetForElements, monitorForElements } from '@atlaskit/pragmatic-drag-and-drop/element/adapter'
import { attachInstruction, extractInstruction } from '@atlaskit/pragmatic-drag-and-drop-hitbox/list-item'
import { DropIndicator } from '@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/list-item'
import { reorder } from '@atlaskit/pragmatic-drag-and-drop/reorder'
```

2. Add a `SegmentCard` sub-component (before the main page component):

```tsx
function SegmentCard({
  seg,
  index,
  total,
  onUpdate,
  onRemove,
}: {
  seg: Segment
  index: number
  total: number
  onUpdate: (key: string, value: unknown) => void
  onRemove: () => void
}) {
  const cardRef = useRef<HTMLDivElement>(null)
  const handleRef = useRef<HTMLDivElement>(null)
  const [closestEdge, setClosestEdge] = useState<'top' | 'bottom' | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    const card = cardRef.current
    const handle = handleRef.current
    if (!card || !handle) return

    return combine(
      draggable({
        element: card,
        dragHandle: handle,
        getInitialData: () => ({ type: 'segment', index }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
      }),
      dropTargetForElements({
        element: card,
        canDrop: ({ source }) => source.data.type === 'segment' && source.data.index !== index,
        getData: ({ input, element }) =>
          attachInstruction({ type: 'segment', index }, {
            element,
            input,
            operations: { 'reorder-before': 'available', 'reorder-after': 'available' },
            axis: 'vertical',
          }),
        onDrag: ({ self }) => {
          const instruction = extractInstruction(self.data)
          setClosestEdge(instruction ? (instruction.operation === 'reorder-before' ? 'top' : 'bottom') : null)
        },
        onDragLeave: () => setClosestEdge(null),
        onDrop: () => setClosestEdge(null),
      }),
    )
  }, [index])

  return (
    <div
      ref={cardRef}
      className={`relative rounded border p-4 flex flex-col gap-3 ${isDragging ? 'opacity-40' : ''}`}
    >
      {closestEdge && <DropIndicator edge={closestEdge} />}
      <div className="flex items-center gap-2">
        <div
          ref={handleRef}
          className="cursor-grab text-muted-foreground select-none px-1 text-lg"
          title="拖拽排序"
        >
          ⠿
        </div>
        <Input
          className="flex-1"
          value={seg.title}
          onChange={(e) => onUpdate('title', e.target.value)}
          placeholder="阶段名称，如：产品介绍、限时促单"
        />
        <span className="text-xs text-muted-foreground w-6 text-right">{index + 1}/{total}</span>
        <Button variant="ghost" size="sm" onClick={onRemove}>×</Button>
      </div>
      <textarea
        className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        value={seg.goal}
        onChange={(e) => onUpdate('goal', e.target.value)}
        rows={2}
        placeholder="告诉 AI 这段做什么，如：重点介绍益生菌成分，引导观众点购物车"
      />
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">锚点话术（AI 会在合适时机自然说出）</span>
        <TagInput
          value={seg.cue}
          onChange={(v) => onUpdate('cue', v)}
          placeholder="回车添加，AI 会在合适时机自然融入"
        />
      </div>
      <div className="flex gap-4 items-center text-sm flex-wrap">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={seg.must_say}
            onChange={(e) => onUpdate('must_say', e.target.checked)}
          />
          锚点话术必须全部说完
        </label>
        <label className="flex items-center gap-2">
          时长(秒)
          <Input
            type="number"
            className="w-20"
            value={seg.duration}
            onChange={(e) => onUpdate('duration', Number(e.target.value))}
          />
        </label>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">关键词</span>
        <TagInput value={seg.keywords} onChange={(v) => onUpdate('keywords', v)} placeholder="回车添加" />
      </div>
    </div>
  )
}
```

3. Replace the script tab body (the `{activeTab === 'script' && ...}` block) with:

```tsx
{activeTab === 'script' && (
  <div className="flex flex-col gap-3" ref={listRef}>
    {plan.script.segments.map((seg, i) => (
      <SegmentCard
        key={seg.id}
        seg={seg}
        index={i}
        total={plan.script.segments.length}
        onUpdate={(key, value) => updateSegment(i, key, value)}
        onRemove={() => removeSegment(i)}
      />
    ))}
    <Button variant="outline" className="self-start" onClick={addSegment}>+ 添加段落</Button>
  </div>
)}
```

4. Add `listRef` and `monitorForElements` effect to the main component, and update `addSegment` to use new fields:

```tsx
const listRef = useRef<HTMLDivElement>(null)

useEffect(() => {
  return monitorForElements({
    canMonitor: ({ source }) => source.data.type === 'segment',
    onDrop({ source, location }) {
      if (!plan) return
      const target = location.current.dropTargets[0]
      if (!target) return
      const instruction = extractInstruction(target.data)
      if (!instruction) return
      const startIndex = source.data.index as number
      const targetIndex = target.data.index as number
      const reordered = reorder({
        list: plan.script.segments,
        startIndex,
        finishIndex: instruction.operation === 'reorder-before'
          ? targetIndex
          : targetIndex + 1 > plan.script.segments.length - 1 ? plan.script.segments.length - 1 : targetIndex,
      })
      savePlan({ ...plan, script: { segments: reordered } })
    },
  })
}, [plan, savePlan])
```

5. Update `addSegment` to use new fields:

```tsx
function addSegment() {
  if (!plan) return
  const newSeg: Segment = {
    id: `seg-${Date.now()}`,
    title: '',
    goal: '',
    duration: 300,
    cue: [],
    must_say: false,
    keywords: [],
  }
  savePlan({ ...plan, script: { segments: [...plan.script.segments, newSeg] } })
}
```

6. Remove `moveSegment` function (no longer needed with drag-and-drop).

- [ ] **Step 4: Run type check**

```bash
cd apps/web && pnpm tsc --noEmit
```

Expected: zero output (no errors).

- [ ] **Step 5: Run tests**

```bash
cd apps/web && pnpm test --run
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app/\(dashboard\)/live/plans/\[id\]/
git commit -m "feat: rewrite segment editor with title/goal/cue fields and drag-and-drop sorting"
```

---

### Task 6: Update seed script

**Files:**
- Modify: `scripts/seed_plans.py`

Update the sample plan to use the new segment structure (`title`, `goal`, `cue`, `must_say`), with realistic durations. Then re-seed the database.

- [ ] **Step 1: Update `SAMPLE_PLAN` segments in `scripts/seed_plans.py`**

Replace the entire `"script"` section of `SAMPLE_PLAN`:

```python
    "script": {
        "segments": [
            {
                "id": "s1",
                "title": "开场预热",
                "goal": "欢迎新进来的观众，自我介绍，告诉大家今天直播主题是护肤好物分享。引导点关注、开小黄车，营造轻松氛围。",
                "duration": 300,
                "cue": [],
                "must_say": False,
                "keywords": ["关注", "小黄车", "今天带来"],
            },
            {
                "id": "s2",
                "title": "产品介绍",
                "goal": "重点讲解益生菌修护屏障、72小时补水、0酒精0香精适合敏感肌。结合自身使用体验，回应弹幕里的皮肤问题，引导观众点击购物车。",
                "duration": 1200,
                "cue": [
                    "2000亿活性益生菌，专门修护皮肤屏障",
                    "72小时持续补水，上脸不黏腻",
                    "0酒精0香精，敏感肌亲测可用",
                ],
                "must_say": False,
                "keywords": ["益生菌", "屏障", "敏感肌", "72小时", "购物车"],
            },
            {
                "id": "s3",
                "title": "互动答疑",
                "goal": "专门回答弹幕里的产品问题：成分、用法、适合肤质、与其他产品叠加顺序等。保持轻松对话感，鼓励观众把问题打在弹幕里。",
                "duration": 900,
                "cue": [],
                "must_say": False,
                "keywords": ["问题", "成分", "用法", "敏感肌", "孕妇"],
            },
            {
                "id": "s4",
                "title": "限时促单",
                "goal": "制造紧迫感，引导立即下单。",
                "duration": 300,
                "cue": [
                    "直播间专属价299，原价399",
                    "买正装送同款旅行小样",
                    "库存不多了，家人们冲",
                ],
                "must_say": True,
                "keywords": ["299", "限时", "库存", "小样", "下单"],
            },
            {
                "id": "s5",
                "title": "产品介绍（第二轮）",
                "goal": "新进来的观众较多，重新介绍产品卖点，侧重真实使用感受和对比其他同类产品的差异。继续响应弹幕，保持场子热度。",
                "duration": 1200,
                "cue": [
                    "2000亿活性益生菌，专门修护皮肤屏障",
                    "72小时持续补水，上脸不黏腻",
                ],
                "must_say": False,
                "keywords": ["益生菌", "对比", "使用感受", "购物车"],
            },
            {
                "id": "s6",
                "title": "互动游戏",
                "goal": "发起弹幕互动：让观众打出自己的肤质，按肤质给出不同的护肤建议，顺带植入产品适用场景。气氛活跃后再引导下单。",
                "duration": 600,
                "cue": [],
                "must_say": False,
                "keywords": ["肤质", "弹幕", "互动", "护肤建议"],
            },
            {
                "id": "s7",
                "title": "第二次促单",
                "goal": "再次强调直播间价格优惠和赠品，提醒库存告急，给还在犹豫的观众最后一推。",
                "duration": 300,
                "cue": [
                    "直播间专属价299，原价399",
                    "买正装送同款旅行小样",
                    "最后机会，库存告急",
                ],
                "must_say": True,
                "keywords": ["299", "赠品", "库存", "最后机会"],
            },
            {
                "id": "s8",
                "title": "收尾预告",
                "goal": "感谢今天的观众和下单的宝宝，预告下次直播时间和主题，引导关注账号，温馨道别。",
                "duration": 300,
                "cue": [],
                "must_say": False,
                "keywords": ["感谢", "下次直播", "关注", "再见"],
            },
        ]
    },
```

- [ ] **Step 2: Delete old seed data and re-seed**

```bash
source .venv/bin/activate && python3 -c "
import asyncio, aiosqlite
async def delete():
    async with aiosqlite.connect('vision.db') as conn:
        await conn.execute(\"DELETE FROM live_plans WHERE name = '示例方案 · 瑷尔博士水乳套装'\")
        await conn.commit()
        print('[ok] deleted old sample plan')
asyncio.run(delete())
" && python scripts/seed_plans.py
```

Expected:
```
[ok] deleted old sample plan
[ok]   Created plan: '示例方案 · 瑷尔博士水乳套装'  id=...
```

- [ ] **Step 3: Run full backend test suite**

```bash
source .venv/bin/activate && pytest src/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_plans.py
git commit -m "chore: update seed plan segments to new title/goal/cue structure"
```

---

## Self-Review

**Spec coverage:**
- ✅ `ScriptSegment` fields: `title`, `goal`, `cue`, `must_say` — Task 1
- ✅ `interruptible` removed — Task 1
- ✅ AI prompt restructured with `title`/`goal`/`cue`/`must_say` sections — Task 2
- ✅ `must_say=True` → "必须全部逐字说出", `False` → "尽量覆盖" — Task 2
- ✅ Migration: old `text` → `goal`, `title` → "段落N" in `plan_store.get()` — Task 3
- ✅ `session.py` segment construction updated — Task 3
- ✅ Frontend `Segment` type updated — Task 4
- ✅ DnD packages installed — Task 4
- ✅ Segment editor UI: new fields, drag handle, `DropIndicator`, `monitorForElements` — Task 5
- ✅ Up/down buttons removed — Task 5
- ✅ Seed data updated to new structure — Task 6

**Placeholder scan:** None found.

**Type consistency:** `Segment.cue: string[]` in frontend matches `ScriptSegment.cue: list[str]` in backend. `must_say` consistent throughout. `title`/`goal` consistent in schema, session, plan_store, prompt builder, and frontend.
