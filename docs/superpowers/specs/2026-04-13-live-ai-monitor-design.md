# Live AI Monitor — Design Spec

**Goal:** 在直播控场页面的主控区域展示 AI 实时状态、脚本进度，并提供脚本粗粒度跳转控制。

**Architecture:** 新增 `useAiMonitor` hook 消费 SSE 中的 `tts_output` 和 `script` 事件；后端新增两个路由支持脚本前进/后退；主控区域拆成左右两栏（脚本控制 + AI 日志）。

**Tech Stack:** Next.js App Router, React, Tailwind CSS v4, shadcn/ui, FastAPI

---

## 数据层

### 前端：`useAiMonitor` hook

新文件：`apps/web/src/features/live/hooks/use-ai-monitor.ts`

复用 `useLiveStream` 已建立的 SSE 连接不合适（两个 hook 各自持有独立连接会产生两条 SSE 流）。正确做法是在 `useLiveStream` 内部同时处理 `tts_output` 和 `script` 事件，通过返回值暴露给页面。

修改 `use-live-stream.ts`，新增返回字段：

```ts
// 新增类型
export type AiOutput = {
  content: string
  source: 'script' | 'agent' | 'inject'
  speech_prompt: string
  ts: number
}

export type ScriptState = {
  segment_id: string
  remaining_seconds: number
  finished: boolean
}

// useLiveStream 新增返回值
return {
  events,          // 现有
  connected,       // 现有
  onlineCount,     // 现有
  aiOutputs,       // AiOutput[]，最多 200 条，sessionStorage 缓存
  scriptState,     // ScriptState | null
}
```

**缓存策略：**
- `aiOutputs` 用 `sessionStorage` 持久化（key: `live_ai_outputs_cache`），最多 200 条，append-only
- `scriptState` 不缓存（实时状态，后端每 5 秒广播一次，重连后自动恢复）

### 后端：脚本跳转 API

新增两个路由到 `src/api/routes.py`：

```
POST /live/script/next   — 跳到下一段
POST /live/script/prev   — 跳到上一段
```

`ScriptRunner` 新增两个方法：

```python
def advance(self) -> None:
    """跳到下一段，若已是最后一段则不操作。"""

def rewind(self) -> None:
    """跳到上一段，若已是第一段则不操作。"""
```

两个路由返回当前 session state（和 `/live/state` 格式一致），会话未运行时返回 400。

---

## UI 层

### 页面布局变更

`apps/web/src/app/(dashboard)/live/page.tsx`

```
┌─────────────────────────────────────────────────────────────────────┐
│ 顶部 bar：直播控场  ● 直播中  product_core  剩余 1:23  队列 2  [停止]│
├────────────────────────────────┬──────────────────┬─────────────────┤
│         主控区域（左）          │   AI 日志（中）   │  弹幕面板（右） │
│  ┌──────────────────────────┐  │                  │                 │
│  │ 脚本进度卡               │  │ [script] 大家好… │ 全部 弹幕 礼物  │
│  │ segment_id  剩余 1:23    │  │ [agent]  感谢…   │                 │
│  │ ████████░░░░             │  │ [inject] 限时…   │ 用户A: 弹幕内容 │
│  │ 段落文本（截断）          │  │ （滚动）          │ 用户B 进场      │
│  │ [← 上一段]  [下一段 →]   │  │                  │ ...             │
│  └──────────────────────────┘  │                  │                 │
│  ┌──────────────────────────┐  │                  │                 │
│  │ 当前 AI 状态              │  │                  │                 │
│  │ ● 正在说：「今天这款…」   │  │                  │                 │
│  │ 队列 2 句  来源 agent     │  │                  │                 │
│  └──────────────────────────┘  │                  │                 │
└────────────────────────────────┴──────────────────┴─────────────────┘
```

三栏宽度比例：左 `w-72`、中 `flex-1`、右 `w-96`（现有）。

### 新增组件

**1. `ScriptCard`** — `apps/web/src/features/live/components/script-card.tsx`

- 显示当前段落 ID、剩余时间、段落文本（截断至 2 行）
- 进度条：`remaining_seconds / segment_duration`（segment_duration 从后端 state 获取，需后端在 script 事件中补充）
- 上一段 / 下一段按钮，调用 `POST /live/script/prev` 和 `POST /live/script/next`
- 会话未运行时按钮 disabled

**2. `AiStatusCard`** — `apps/web/src/features/live/components/ai-status-card.tsx`

- 显示最新一条 `tts_output` 的 content（当前正在说/最近说的）
- 显示 `queue_depth`（来自 `/live/state` 轮询，现有逻辑已有）
- 显示 source badge（script / agent / inject）

**3. `AiOutputLog`** — `apps/web/src/features/live/components/ai-output-log.tsx`

- 复用 `useScrollAnchor` hook（和弹幕面板相同的滚动锚点逻辑）
- 每条记录：source badge + content + 时间戳
- source 颜色：`script` 蓝色、`agent` 紫色、`inject` 橙色
- 最多显示 200 条，append-only，`sessionStorage` 缓存

### source badge 颜色规范

| source  | badge 样式 |
|---------|-----------|
| script  | `bg-blue-500/15 text-blue-600 dark:text-blue-400` |
| agent   | `bg-violet-500/15 text-violet-600 dark:text-violet-400` |
| inject  | `bg-orange-500/15 text-orange-600 dark:text-orange-400` |

---

## 后端变更细节

### `ScriptRunner.advance()` / `rewind()`

```python
def advance(self) -> None:
    with self._lock:
        if self._idx < len(self._segments) - 1:
            self._idx += 1
            self._elapsed = 0.0

def rewind(self) -> None:
    with self._lock:
        if self._idx > 0:
            self._idx -= 1
            self._elapsed = 0.0
```

`_idx` 和 `_elapsed` 已存在于 `ScriptRunner`，只需加方法和路由。

### script 事件补充 `segment_duration`

当前 `script` SSE 事件只有 `segment_id` 和 `remaining_seconds`，前端进度条需要知道总时长。后端广播时补充 `segment_duration`：

```python
# 在 ScriptRunner._broadcast() 中
{
  "type": "script",
  "segment_id": seg.id,
  "remaining_seconds": remaining,
  "segment_duration": seg.duration,   # 新增
  "finished": self._finished,
  "ts": time.time(),
}
```

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `src/live/script_runner.py` | 新增 `advance()` / `rewind()` 方法，`_broadcast()` 补充 `segment_duration` |
| `src/api/routes.py` | 新增 `POST /live/script/next` 和 `POST /live/script/prev` |
| `apps/web/src/features/live/hooks/use-live-stream.ts` | 新增 `tts_output` / `script` 事件处理，返回 `aiOutputs` 和 `scriptState` |
| `apps/web/src/features/live/components/script-card.tsx` | 新建 |
| `apps/web/src/features/live/components/ai-status-card.tsx` | 新建 |
| `apps/web/src/features/live/components/ai-output-log.tsx` | 新建 |
| `apps/web/src/app/(dashboard)/live/page.tsx` | 三栏布局，接入新组件 |
