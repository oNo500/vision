# Live AI Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在直播控场页面主控区域展示 AI 实时状态、TTS 输出日志、脚本段落进度，并提供上一段/下一段跳转控制。

**Architecture:** 后端在 `ScriptRunner` 新增 `advance()`/`rewind()` 方法 + 两条路由，`_broadcast_script_state` 补充 `segment_duration` 字段；前端扩展 `useLiveStream` 消费 `tts_output` / `script` SSE 事件，新建三个展示组件（`ScriptCard`、`AiStatusCard`、`AiOutputLog`），页面改为三栏布局。

**Tech Stack:** Python 3.12, FastAPI, pytest; Next.js 16 App Router, React 19, Tailwind CSS v4, TypeScript 5, Vitest

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/live/script_runner.py` | Modify | 新增 `advance()` / `rewind()` 方法 |
| `src/live/session.py` | Modify | `_broadcast_script_state` 补充 `segment_duration` |
| `src/live/routes.py` | Modify | 新增 `POST /live/script/next` 和 `POST /live/script/prev` |
| `tests/live/test_script_runner.py` | Modify | 新增 advance/rewind 测试 |
| `apps/web/src/features/live/hooks/use-live-stream.ts` | Modify | 消费 `tts_output` / `script` 事件，返回 `aiOutputs` / `scriptState` |
| `apps/web/src/features/live/components/script-card.tsx` | Create | 脚本进度卡 + 前进/后退按钮 |
| `apps/web/src/features/live/components/ai-status-card.tsx` | Create | 当前 AI 状态（最新台词 + 队列深度 + 来源） |
| `apps/web/src/features/live/components/ai-output-log.tsx` | Create | TTS 输出滚动日志 |
| `apps/web/src/app/(dashboard)/live/page.tsx` | Modify | 三栏布局接入新组件 |

---

## Task 1: ScriptRunner advance/rewind

**Files:**
- Modify: `src/live/script_runner.py`
- Modify: `tests/live/test_script_runner.py`

- [ ] **Step 1: 写失败测试**

在 `tests/live/test_script_runner.py` 末尾追加：

```python
def test_advance_skips_to_next_segment():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.advance()
    state = runner.get_state()
    assert state["segment_id"] == "core"
    assert state["remaining_seconds"] > 0


def test_advance_at_last_segment_does_nothing():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.advance()  # opening → core
    runner.advance()  # core → closing
    runner.advance()  # closing → no-op (last)
    state = runner.get_state()
    assert state["segment_id"] == "closing"


def test_rewind_goes_to_previous_segment():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.advance()  # → core
    runner.rewind()   # → opening
    state = runner.get_state()
    assert state["segment_id"] == "opening"


def test_rewind_at_first_segment_does_nothing():
    script = LiveScript.from_dict(SAMPLE_DATA)
    runner = ScriptRunner(script)
    runner.rewind()  # no-op
    state = runner.get_state()
    assert state["segment_id"] == "opening"
```

- [ ] **Step 2: 确认测试失败**

```bash
cd /Users/xiu/code/vision
uv run pytest tests/live/test_script_runner.py::test_advance_skips_to_next_segment -v
```

Expected: `FAILED` with `AttributeError: 'ScriptRunner' object has no attribute 'advance'`

- [ ] **Step 3: 实现 advance() / rewind()**

在 `src/live/script_runner.py` 的 `stop()` 方法后、`get_state()` 方法前插入：

```python
def advance(self) -> None:
    """Skip to the next segment immediately (thread-safe)."""
    with self._lock:
        if self._index < len(self._script.segments) - 1:
            self._index += 1
            self._segment_start = time.monotonic()

def rewind(self) -> None:
    """Jump back to the previous segment (thread-safe)."""
    with self._lock:
        if self._index > 0:
            self._index -= 1
            self._segment_start = time.monotonic()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/live/test_script_runner.py -v
```

Expected: 全部 PASS（原有 5 条 + 新增 4 条 = 9 条）

- [ ] **Step 5: Commit**

```bash
git add src/live/script_runner.py tests/live/test_script_runner.py
git commit -m "feat(live): add ScriptRunner.advance() and rewind()"
```

---

## Task 2: 后端路由 + segment_duration 广播

**Files:**
- Modify: `src/live/routes.py`
- Modify: `src/live/session.py`

- [ ] **Step 1: 在 routes.py 新增两条路由**

在 `inject` 路由后追加：

```python
@router.post("/script/next")
def script_next(sm: SessionManager = Depends(get_session_manager)) -> dict:
    runner = sm.get_script_runner()
    if runner is None:
        raise HTTPException(status_code=400, detail="Session not running")
    runner.advance()
    return sm.get_state()


@router.post("/script/prev")
def script_prev(sm: SessionManager = Depends(get_session_manager)) -> dict:
    runner = sm.get_script_runner()
    if runner is None:
        raise HTTPException(status_code=400, detail="Session not running")
    runner.rewind()
    return sm.get_state()
```

- [ ] **Step 2: 在 SessionManager 新增 get_script_runner()**

在 `session.py` 的 `inject()` 方法后插入：

```python
def get_script_runner(self) -> ScriptRunner | None:
    with self._lock:
        return self._script_runner if self._running else None
```

- [ ] **Step 3: 补充 segment_duration 到广播事件**

在 `session.py` 的 `_broadcast_script_state` 内部函数中，将：

```python
self._bus.publish({
    "type": "script",
    "segment_id": state.get("segment_id"),
    "remaining_seconds": state.get("remaining_seconds", 0),
    "ts": time.time(),
})
```

改为：

```python
self._bus.publish({
    "type": "script",
    "segment_id": state.get("segment_id"),
    "remaining_seconds": state.get("remaining_seconds", 0),
    "segment_duration": state.get("segment_duration", 0),
    "ts": time.time(),
})
```

- [ ] **Step 4: get_state() 补充 segment_duration**

在 `src/live/script_runner.py` 的 `get_state()` 返回值 dict 中，加入 `segment_duration`：

当前代码：
```python
return {
    "segment_id": seg.id,
    "segment_text": seg.text,
    "interruptible": seg.interruptible,
    "keywords": seg.keywords,
    "remaining_seconds": remaining,
    "finished": False,
}
```

改为：
```python
return {
    "segment_id": seg.id,
    "segment_text": seg.text,
    "interruptible": seg.interruptible,
    "keywords": seg.keywords,
    "remaining_seconds": remaining,
    "segment_duration": seg.duration,
    "finished": False,
}
```

- [ ] **Step 5: 手动验证路由**

确保 API 已启动（`make api`），然后：

```bash
curl -s -X POST http://localhost:8000/live/script/next | python3 -m json.tool
```

Expected（session 未运行时）：`{"detail": "Session not running"}`

- [ ] **Step 6: Commit**

```bash
git add src/live/routes.py src/live/session.py src/live/script_runner.py
git commit -m "feat(live): add script next/prev routes and segment_duration to broadcast"
```

---

## Task 3: 前端扩展 useLiveStream

**Files:**
- Modify: `apps/web/src/features/live/hooks/use-live-stream.ts`

当前 `SKIP_TYPES` 包含 `tts_output` 需移除；`script` 事件目前未处理。

- [ ] **Step 1: 更新 use-live-stream.ts**

用以下内容完整替换 `apps/web/src/features/live/hooks/use-live-stream.ts`：

```typescript
'use client'

import { useEffect, useRef, useState } from 'react'

import { env } from '@/config/env'

export type LiveEvent = {
  type: string
  user: string
  text: string | null
  gift: string | null
  value: number
  is_follower: boolean
  ts: number
}

export type AiOutput = {
  content: string
  source: 'script' | 'agent' | 'inject'
  speech_prompt: string
  ts: number
}

export type ScriptState = {
  segment_id: string
  remaining_seconds: number
  segment_duration: number
  finished: boolean
}

const MAX_EVENTS = 200
const SKIP_TYPES = new Set(['ping', 'agent', 'script', 'tts_output'])
const EVENTS_KEY = 'live_events_cache'
const AI_OUTPUTS_KEY = 'live_ai_outputs_cache'

function loadCache<T>(key: string): T[] {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return []
    return JSON.parse(raw) as T[]
  } catch {
    return []
  }
}

function saveCache<T>(key: string, items: T[]): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(items))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

export function useLiveStream() {
  const [events, setEvents] = useState<LiveEvent[]>(() => loadCache<LiveEvent>(EVENTS_KEY))
  const [aiOutputs, setAiOutputs] = useState<AiOutput[]>(() => loadCache<AiOutput>(AI_OUTPUTS_KEY))
  const [scriptState, setScriptState] = useState<ScriptState | null>(null)
  const [connected, setConnected] = useState(false)
  const [onlineCount, setOnlineCount] = useState<number | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource(`${env.NEXT_PUBLIC_API_URL}/live/stream`)
    esRef.current = es

    es.onopen = () => setConnected(true)

    es.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data) as Record<string, unknown>
        const type = raw['type'] as string

        if (type === 'ping' || type === 'agent') return

        if (type === 'stats') {
          setOnlineCount(raw['value'] as number)
          return
        }

        if (type === 'script') {
          setScriptState({
            segment_id: raw['segment_id'] as string,
            remaining_seconds: raw['remaining_seconds'] as number,
            segment_duration: (raw['segment_duration'] as number) ?? 0,
            finished: (raw['finished'] as boolean) ?? false,
          })
          return
        }

        if (type === 'tts_output') {
          const output: AiOutput = {
            content: raw['content'] as string,
            source: raw['source'] as AiOutput['source'],
            speech_prompt: (raw['speech_prompt'] as string) ?? '',
            ts: raw['ts'] as number,
          }
          setAiOutputs((prev) => {
            const next = [...prev, output]
            const trimmed = next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next
            saveCache(AI_OUTPUTS_KEY, trimmed)
            return trimmed
          })
          return
        }

        // live interaction events
        if (SKIP_TYPES.has(type)) return
        const event = raw as unknown as LiveEvent
        setEvents((prev) => {
          const next = [...prev, event]
          const trimmed = next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next
          saveCache(EVENTS_KEY, trimmed)
          return trimmed
        })
      } catch {
        // ignore malformed frames
      }
    }

    es.onerror = () => setConnected(false)

    return () => {
      es.close()
      esRef.current = null
      setConnected(false)
    }
  }, [])

  return { events, connected, onlineCount, aiOutputs, scriptState }
}
```

- [ ] **Step 2: 类型检查**

```bash
cd /Users/xiu/code/vision
pnpm --filter web typecheck
```

Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/live/hooks/use-live-stream.ts
git commit -m "feat(live): consume tts_output and script events in useLiveStream"
```

---

## Task 4: ScriptCard 组件

**Files:**
- Create: `apps/web/src/features/live/components/script-card.tsx`

- [ ] **Step 1: 创建 script-card.tsx**

```typescript
'use client'

import { useState } from 'react'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'

import { env } from '@/config/env'
import type { ScriptState } from '../hooks/use-live-stream'

interface ScriptCardProps {
  scriptState: ScriptState | null
  running: boolean
}

async function postScriptNav(direction: 'next' | 'prev'): Promise<void> {
  await fetch(`${env.NEXT_PUBLIC_API_URL}/live/script/${direction}`, { method: 'POST' })
}

export function ScriptCard({ scriptState, running }: ScriptCardProps) {
  const [loading, setLoading] = useState(false)

  async function handleNav(direction: 'next' | 'prev') {
    if (!running || loading) return
    setLoading(true)
    try {
      await postScriptNav(direction)
    } finally {
      setLoading(false)
    }
  }

  const progress =
    scriptState && scriptState.segment_duration > 0
      ? ((scriptState.segment_duration - scriptState.remaining_seconds) / scriptState.segment_duration) * 100
      : 0

  const remaining = scriptState
    ? `${Math.floor(scriptState.remaining_seconds / 60)}:${String(Math.floor(scriptState.remaining_seconds % 60)).padStart(2, '0')}`
    : '--:--'

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">脚本进度</span>
        {scriptState?.segment_id && (
          <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-foreground">
            {scriptState.segment_id}
          </span>
        )}
      </div>

      {/* progress bar */}
      <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-1000"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mb-3 text-right text-xs tabular-nums text-muted-foreground">剩余 {remaining}</div>

      {/* segment text */}
      <p className={cn(
        'mb-4 line-clamp-2 text-sm leading-relaxed text-foreground',
        !scriptState && 'text-muted-foreground',
      )}>
        {scriptState?.segment_id ? '（脚本运行中）' : '未开始'}
      </p>

      {/* nav buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={!running || loading}
          onClick={() => handleNav('prev')}
        >
          <ChevronLeftIcon className="mr-1 size-3.5" />
          上一段
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={!running || loading}
          onClick={() => handleNav('next')}
        >
          下一段
          <ChevronRightIcon className="ml-1 size-3.5" />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 类型检查**

```bash
pnpm --filter web typecheck
```

Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/live/components/script-card.tsx
git commit -m "feat(live): add ScriptCard component"
```

---

## Task 5: AiStatusCard 组件

**Files:**
- Create: `apps/web/src/features/live/components/ai-status-card.tsx`

- [ ] **Step 1: 创建 ai-status-card.tsx**

```typescript
import { cn } from '@workspace/ui/lib/utils'

import type { AiOutput } from '../hooks/use-live-stream'

const SOURCE_CFG = {
  script: { label: 'script', cls: 'bg-blue-500/15 text-blue-600 dark:text-blue-400' },
  agent:  { label: 'agent',  cls: 'bg-violet-500/15 text-violet-600 dark:text-violet-400' },
  inject: { label: 'inject', cls: 'bg-orange-500/15 text-orange-600 dark:text-orange-400' },
} as const

interface AiStatusCardProps {
  latest: AiOutput | null
  queueDepth: number
}

export function AiStatusCard({ latest, queueDepth }: AiStatusCardProps) {
  const sourceCfg = latest ? SOURCE_CFG[latest.source] : null

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">AI 状态</span>
        <span className={cn(
          'text-xs tabular-nums',
          queueDepth > 0 ? 'text-foreground' : 'text-muted-foreground',
        )}>
          队列 {queueDepth} 句
        </span>
      </div>

      {latest ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
            {sourceCfg && (
              <span className={cn('rounded px-1.5 py-px text-[10px] font-medium leading-none', sourceCfg.cls)}>
                {sourceCfg.label}
              </span>
            )}
          </div>
          <p className="line-clamp-2 text-sm leading-relaxed text-foreground">
            {latest.content}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">等待 AI 输出…</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 类型检查**

```bash
pnpm --filter web typecheck
```

Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/live/components/ai-status-card.tsx
git commit -m "feat(live): add AiStatusCard component"
```

---

## Task 6: AiOutputLog 组件

**Files:**
- Create: `apps/web/src/features/live/components/ai-output-log.tsx`

- [ ] **Step 1: 创建 ai-output-log.tsx**

```typescript
'use client'

import { useEffect } from 'react'

import { cn } from '@workspace/ui/lib/utils'
import { ArrowDownIcon } from 'lucide-react'

import type { AiOutput } from '../hooks/use-live-stream'
import { useScrollAnchor } from '../hooks/use-scroll-anchor'

const SOURCE_CFG = {
  script: { label: 'script', cls: 'bg-blue-500/15 text-blue-600 dark:text-blue-400' },
  agent:  { label: 'agent',  cls: 'bg-violet-500/15 text-violet-600 dark:text-violet-400' },
  inject: { label: 'inject', cls: 'bg-orange-500/15 text-orange-600 dark:text-orange-400' },
} as const

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function OutputRow({ output }: { output: AiOutput }) {
  const cfg = SOURCE_CFG[output.source]
  return (
    <div className="group flex items-start gap-2.5 px-3 py-2.5 transition-colors hover:bg-muted/40">
      <span className={cn('mt-0.5 shrink-0 rounded px-1.5 py-px text-[10px] font-medium leading-none', cfg.cls)}>
        {cfg.label}
      </span>
      <p className="min-w-0 flex-1 text-sm leading-relaxed text-foreground">{output.content}</p>
      <span className="shrink-0 pt-0.5 text-[10px] tabular-nums text-muted-foreground/60">
        {formatTime(output.ts)}
      </span>
    </div>
  )
}

interface AiOutputLogProps {
  outputs: AiOutput[]
}

export function AiOutputLog({ outputs }: AiOutputLogProps) {
  const { scrollRef, isAtBottom, unread, scrollToBottom, onNewMessage } = useScrollAnchor()

  useEffect(() => {
    if (outputs.length > 0) onNewMessage()
  }, [outputs.length, onNewMessage])

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border bg-background">
      <div className="shrink-0 border-b px-3 py-2">
        <span className="text-sm font-semibold">AI 输出</span>
      </div>

      <div className="relative min-h-0 flex-1">
        <div ref={scrollRef} className="absolute inset-0 overflow-y-auto py-1">
          {outputs.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <span className="text-sm text-muted-foreground">等待 AI 输出…</span>
            </div>
          ) : (
            outputs.map((output, i) => (
              <OutputRow key={`${output.ts}-${i}`} output={output} />
            ))
          )}
        </div>

        {!isAtBottom && (
          <button
            type="button"
            onClick={() => scrollToBottom()}
            className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border bg-background/95 px-3 py-1.5 text-xs font-medium shadow-lg backdrop-blur-sm transition-all hover:bg-muted active:scale-95"
          >
            <ArrowDownIcon className="size-3" />
            {unread > 0 ? `${unread} 条新输出` : '跳到最新'}
          </button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 类型检查**

```bash
pnpm --filter web typecheck
```

Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/live/components/ai-output-log.tsx
git commit -m "feat(live): add AiOutputLog component"
```

---

## Task 7: 页面三栏布局

**Files:**
- Modify: `apps/web/src/app/(dashboard)/live/page.tsx`

- [ ] **Step 1: 更新 page.tsx**

用以下内容完整替换 `apps/web/src/app/(dashboard)/live/page.tsx`：

```typescript
'use client'

import { AiOutputLog } from '@/features/live/components/ai-output-log'
import { AiStatusCard } from '@/features/live/components/ai-status-card'
import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { ScriptCard } from '@/features/live/components/script-card'
import { SessionControls } from '@/features/live/components/session-controls'
import { useLiveSession } from '@/features/live/hooks/use-live-session'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const session = useLiveSession()
  const { events, connected, onlineCount, aiOutputs, scriptState } = useLiveStream()

  const latestOutput = aiOutputs.length > 0 ? aiOutputs[aiOutputs.length - 1] ?? null : null

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* top bar */}
      <div className="shrink-0 border-b px-5 py-3">
        <div className="flex items-center gap-4">
          <h1 className="shrink-0 text-sm font-semibold">直播控场</h1>
          <div className="flex-1">
            <SessionControls {...session} />
          </div>
        </div>
      </div>

      {/* three-column body */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* left: script + AI status */}
        <div className="flex w-72 shrink-0 flex-col gap-3 overflow-auto border-r p-3">
          <ScriptCard scriptState={scriptState} running={session.state.running} />
          <AiStatusCard latest={latestOutput} queueDepth={session.state.queue_depth ?? 0} />
        </div>

        {/* center: AI output log */}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3">
          <AiOutputLog outputs={aiOutputs} />
        </div>

        {/* right: danmaku feed */}
        <div className="flex w-96 shrink-0 flex-col overflow-hidden border-l p-3">
          <DanmakuFeed events={events} connected={connected} onlineCount={onlineCount} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 类型检查**

```bash
pnpm --filter web typecheck
```

Expected: 无错误

- [ ] **Step 3: 截图验证布局**

```bash
agent-browser open http://localhost:3000/live
agent-browser screenshot /tmp/live-ai-monitor.png
```

确认：三栏可见、左栏有脚本卡和状态卡、中栏有 AI 输出日志、右栏有弹幕面板。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/(dashboard)/live/page.tsx
git commit -m "feat(live): three-column layout with AI monitor"
```
