# Session / Danmaku Split + Interrupt Strategy Design

## Goal

Decouple the AI session (DirectorAgent + TTSPlayer + ScriptRunner) from danmaku collection (EventCollector + Orchestrator) so each can be started, stopped, and controlled independently. Add a runtime-switchable interrupt strategy that determines how P0/P1 priority events are handled.

## Architecture

### Two Independent Managers

**`SessionManager`** (AI side — existing, trimmed)
- Owns: ScriptRunner, DirectorAgent, TTSPlayer
- Responsible for: what to say, when to say it, script progression
- Exposes: `tts_queue`, `get_strategy()`, `set_strategy()`
- Does NOT own EventCollector or Orchestrator

**`DanmakuManager`** (new)
- Owns: EventCollector, Orchestrator
- Responsible for: collecting live events, routing by priority
- Receives shared `tts_queue` from SessionManager on construction (for P0/P1 immediate push)
- Receives `get_strategy_fn` callback (reads SessionManager._strategy at call time)
- When SessionManager is not running, P0/P1 immediate push still works if tts_queue is provided; P2/P3 buffer is consumed by nobody (silently accumulates, cleared on restart)

### Interrupt Strategy

Stored on `SessionManager` as `_strategy: Literal["immediate", "intelligent"]`, default `"immediate"`.

**`immediate`** — existing behavior
- P0/P1: Orchestrator pushes hardcoded text directly to `tts_queue`
- Latency: <100ms

**`intelligent`** — new behavior
- P0/P1: Orchestrator puts event into a new `urgent_queue` (separate from `_buffer`)
- DirectorAgent drains `urgent_queue` first at the start of each `_fire()` call, treating urgent events as high-priority context
- Generates personalized LLM response for P0/P1 events
- Latency: 1–3s (LLM call)

`DanmakuManager` reads strategy via `get_strategy_fn()` callback at event-handling time — no restart needed to switch.

### Shared Interfaces

When both managers are running:
- `tts_queue`: shared between SessionManager (TTSPlayer reads) and DanmakuManager (Orchestrator writes on P0/P1 immediate)
- `get_events_fn`: DirectorAgent calls `orchestrator.get_events()` to drain P2/P3 buffer
- `urgent_queue`: SessionManager creates; passed to DanmakuManager for Orchestrator to write; DirectorAgent drains first in intelligent mode

When only SessionManager is running:
- `get_events_fn` returns `[]` (no Orchestrator)
- No `urgent_queue` writes

When only DanmakuManager is running:
- `tts_queue` is None — P0/P1 are silently dropped (no TTS output)
- P2/P3 buffer accumulates but nobody consumes it

## API Endpoints

### New endpoints

```
POST /live/session/start    body: { script, product, mock, project }
POST /live/session/stop
GET  /live/session/state    → { running, segment_id, remaining_seconds, queue_depth, strategy }

POST /live/danmaku/start    body: { cdp_url?, mock? }
POST /live/danmaku/stop
GET  /live/danmaku/state    → { running, buffer_size }

GET  /live/strategy         → { strategy: "immediate" | "intelligent" }
POST /live/strategy         body: { strategy: "immediate" | "intelligent" }
                            → { strategy: "..." }
```

### Deprecated (kept for compatibility)

```
POST /live/start   → calls session/start + danmaku/start together
POST /live/stop    → calls session/stop + danmaku/stop together
GET  /live/state   → merged state from both managers
```

### Unchanged

```
POST /live/inject
POST /live/script/next
POST /live/script/prev
GET  /live/stream
GET  /live/history
```

## Frontend Changes

### `use-live-session.ts`

Split into two hooks:
- `useAiSession()` — polls `/live/session/state`, exposes `start()`/`stop()`
- `useDanmakuSession()` — polls `/live/danmaku/state`, exposes `start()`/`stop()`
- `useStrategy()` — fetches `/live/strategy`, exposes `setStrategy()`

### `session-controls.tsx`

Replace single start/stop button with:
- **AI Session row**: status indicator + start/stop button
- **弹幕采集 row**: status indicator + start/stop button
- **插队策略 row** (shown when AI session running): toggle `及时 | 智能`

## Data Flow: intelligent mode P0/P1

```
CDP event (high-value gift) → EventCollector → event_queue
  ↓ _event_put_with_publish
Orchestrator.handle_event(event)
  ↓ strategy == "intelligent"
urgent_queue.put(event)
  ↓
DirectorAgent._fire():
  urgent = urgent_queue.get_nowait() (if any)
  prompt = build_director_prompt(..., urgent_event=urgent)
  → Gemini LLM
  → personalized response pushed to tts_queue
```

## Constraints

- Switching strategy takes effect immediately on next event — no restart required
- DanmakuManager can run without SessionManager (collect only, no TTS)
- SessionManager can run without DanmakuManager (script-only mode)
- urgent_queue is bounded (maxsize=10) to prevent unbounded growth if LLM is slow
- If urgent_queue is full, new P0/P1 events in intelligent mode are dropped with a warning log
