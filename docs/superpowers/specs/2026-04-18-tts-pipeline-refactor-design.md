# TTS Broadcast Pipeline Refactor — Design

> **Status:** Approved (brainstorming phase)
> **Date:** 2026-04-18
> **Scope:** Backend queue data structures + mutation API + frontend pipeline UI

## Problem

The live-streaming AI control panel presents three backend concepts (LLM generating, TTS in_queue, TTS pcm_queue, now-playing, played history) across three loosely-related UI components (`AiStatusCard`, `TtsQueuePanel`, `AiOutputLog`). Users cannot follow a single sentence through its lifecycle, and cannot edit, delete, or reorder sentences that are already queued.

Backend queues are `queue.Queue` — opaque FIFO containers that prevent any mutation beyond enqueue/dequeue.

## Goals

1. Let operators edit, delete, and reorder any sentence that is not currently being spoken.
2. Unify the three loosely-related UI components into one vertical pipeline that mirrors the backend lifecycle.
3. Preserve TTS audio quality (no pops, no underruns, no mid-sentence interruption).

## Non-Goals

- Interrupting the sentence currently being written to the sound card. A dedicated "stop current" button is a future feature, not part of this refactor.
- Cancelling an in-flight Google TTS HTTP call. We let it complete and discard the PCM if the user removed the item in the meantime.
- Cross-container drag-and-drop (pending ↔ synthesized). Each stage is an independent sortable zone.
- "Regenerate with AI" button inside the edit modal. YAGNI.

## Decisions Matrix

| # | Question | Decision |
|---|---|---|
| 1 | Edit purpose | Full rewrite / content replacement (multi-line textarea + char count) |
| 2 | Synthesized-stage capabilities | Add / delete / edit / in-stage reorder. Editing a synthesized item discards the PCM and re-enqueues at the tail of pending. |
| 3 | Drag-and-drop scope | In-stage only. No cross-stage drag. |
| 4 | Urgent-queue display | Red badge on the item inside the pending list. No separate section. |

## Architecture

### Backend: two ordered containers

```
DirectorAgent / inject        urgent_queue
        │                           │
        └──────────┬────────────────┘
                   ▼
         ┌─────────────────────┐        synth thread
         │  in_queue           │ ──────────────────────▶  Google TTS
         │  OrderedItemStore   │                              │
         │  [TtsItem]          │◀─────── on_queued SSE        │
         │  (unbounded)        │                              ▼
         └─────────────────────┘         ┌─────────────────────┐
                                         │  pcm_queue           │
                                         │  OrderedItemStore    │
                                         │  [PcmItem]           │
                                         │  (maxsize=10)        │
                                         └──────────┬──────────┘
                                                    │ playback thread
                                                    ▼
                                          stream.write (blocking)
                                                    │
                                                    ▼
                                               sound card
```

**`OrderedItemStore[T]`** replaces both `queue.Queue` instances. It exposes two API surfaces:

- **Queue-compatible** for producer/consumer threads: `get(timeout)`, `put(item)`, `qsize()`, `task_done()`. Blocking `get()` uses a condition variable so that a `remove()` of the head wakes it up cleanly.
- **Mutation by UUID** for REST endpoints: `remove(id)`, `move(id, to_index)`, `edit(id, mutator)`, `snapshot()`. All operations are O(log n) or better via an `id → item` map. All mutations take the internal lock.

Cross-container operations (editing a synthesized item ⇒ remove from pcm_queue + insert into in_queue) live in `SessionManager`, not inside `OrderedItemStore`. This keeps the container abstraction pure and business orchestration explicit.

### Backend: in-flight tracking

Between `in_queue.get()` and `pcm_queue.put()` in the synthesis thread, an item exists in neither container. A new `in_flight: dict[str, TtsItem]` keeps them visible to mutation calls. `SessionManager.remove_tts(id)` probes all three locations (`in_queue`, `in_flight`, `pcm_queue`). When the hit lands in `in_flight`, it sets a `cancel_flag` on the item; the synthesis thread checks the flag after Google TTS returns and discards the PCM instead of putting it into `pcm_queue`.

### Backend: event model

| Event | Origin | Payload |
|---|---|---|
| `tts_queued` ✅ existing | `in_queue.put` → `on_queued` | `{id, content, speech_prompt, stage: "pending", urgent}` **(payload widened)** |
| `tts_synthesized` 🆕 | `pcm_queue.put` → `on_synthesized` | `{id}` |
| `tts_playing` ✅ existing | `pcm_queue.get` → `on_play` | `{id, content, speech_prompt}` |
| `tts_done` ✅ existing | after `stream.write` → `on_done` | `{id}` |
| `tts_removed` 🆕 | mutation endpoint | `{id, stage}` |
| `tts_edited` 🆕 | mutation endpoint | `{id, new_id?, content, speech_prompt, stage}` |
| `tts_reordered` 🆕 | mutation endpoint | `{stage, ids: string[]}` |

A one-shot `GET /live/tts/queue/snapshot` endpoint is added for SSE reconnect recovery (returns the full pipeline state in one call).

### Backend: REST endpoints

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| `GET` | `/live/tts/queue/snapshot` | — | `[{id, content, speech_prompt, stage, urgent}]` | Used on reconnect |
| `DELETE` | `/live/tts/queue/{id}` | — | `{stage, removed: true}` or 404 | Auto-detects which container holds the item |
| `PATCH` | `/live/tts/queue/{id}` | `{text: string, speech_prompt?: string}` | `{id, new_id?, stage}` | If target in pending → in-place edit. If in synthesized → discard PCM, create new `TtsItem` appended to pending tail, return `new_id`. |
| `POST` | `/live/tts/queue/reorder` | `{stage: "pending"\|"synthesized", ids: string[]}` | `{ok: true}` or 400 | `ids` must match the stage's current id set exactly; partial reorders rejected. |

### Frontend: data layer

`useLiveStream` becomes a single source of truth:

```ts
type PipelineItem = {
  id: string
  content: string
  speech_prompt: string | null
  stage: 'pending' | 'synthesized' | 'playing' | 'done'
  urgent: boolean
  ts?: number
}

const [pipeline, setPipeline] = useState<PipelineItem[]>([])
```

Derived views are memoized:

```ts
const pending      = pipeline.filter(i => i.stage === 'pending')
const synthesized  = pipeline.filter(i => i.stage === 'synthesized')
const nowPlaying   = pipeline.find(i => i.stage === 'playing') ?? null
const history      = pipeline.filter(i => i.stage === 'done').slice(-100)
```

Event-to-state transitions:

| Event | Mutation |
|---|---|
| `tts_queued` | Append with `stage: 'pending'` |
| `tts_synthesized` | Set `stage` of matching id to `'synthesized'` |
| `tts_playing` | Set `stage` of matching id to `'playing'` |
| `tts_done` | Set `stage` of matching id to `'done'` |
| `tts_removed` | Filter out by id |
| `tts_edited` | If `new_id` present: remove old id, append new; else patch content/speech_prompt in place |
| `tts_reordered` | For the given stage, reorder items to match `ids` |

On SSE reconnect the hook fetches `/live/tts/queue/snapshot` and replaces `pipeline`.

### Frontend: components

```
<BroadcastPipeline>                       — replaces AiStatusCard + TtsQueuePanel + AiOutputLog
  <PipelineHeader>                        — LLM light + "待合成 N · 已合成 M · 紧急 K"
  <StageSection title="待合成" stage="pending" items={pending}>
    <PipelineItem × N>                    — hover reveals edit / delete; red dot for urgent
  </StageSection>
  <StageSection title="已合成" stage="synthesized" items={synthesized}>
    <PipelineItem × N>                    — edit triggers confirm dialog (PCM will be discarded)
  </StageSection>
  <NowPlayingCard item={nowPlaying}>
  <HistorySection>                        — collapsed by default, last 100 items
</BroadcastPipeline>
```

Files created under `apps/web/src/features/live/components/`:

- `broadcast-pipeline.tsx` + `.test.tsx`
- `pipeline-header.tsx`
- `stage-section.tsx`
- `pipeline-item.tsx`
- `pipeline-item-editor.tsx`

Files deleted:

- `ai-status-card.tsx` + test
- `tts-queue-panel.tsx` + test
- `ai-output-log.tsx` + test

Drag-and-drop uses `@dnd-kit/core` + `@dnd-kit/sortable` (new dependencies in `apps/web`). Each `StageSection` wraps its own `SortableContext` to prevent cross-stage drag.

Cross-stage animation uses motion's `layoutId={item.id}`. A pending → synthesized transition animates the card sliding between sections. Editing a synthesized item produces a new id; the old card fades out and the new one fades in at the tail of pending.

## Error Handling and Race Conditions

| Scenario | Backend | Frontend UX |
|---|---|---|
| Delete lands while item is being consumed by synth thread | Found in `in_flight` → set `cancel_flag`; synth discards PCM on completion | Optimistic remove; UI stays consistent |
| Edit targets a synthesized item, but playback thread already picked it up | `pcm_queue.remove` under lock returns None → 404 | Toast "已开始播放，无法编辑" |
| Reorder submitted with stale ids | 400 with ids-mismatch code | Toast "顺序已过时，请重试"; hook re-fetches snapshot |
| SSE disconnect and reconnect | No special handling | Hook clears pipeline and rehydrates from snapshot endpoint |
| Edit of an in-flight item | 409 "正在合成中，请稍候" (or 404 if already completed) | Toast surface; operation not retried automatically |

## Testing Strategy

| Layer | Tests |
|---|---|
| `OrderedItemStore` | Concurrency: 10 producers + 10 consumers + 10 mutators converging to a consistent id set. `get()` wakes on head removal. `put` blocks on maxsize and wakes on `remove`. |
| `SessionManager` | Edit synthesized → correct pcm remove + in_queue append. Remove of in-flight item sets cancel_flag and synth path discards. Reorder with mismatched ids rejects. |
| REST routes | 200 / 400 / 404 / 409 paths; malformed JSON; snapshot endpoint returns expected shape. |
| `useLiveStream` | All seven event types map to the correct pipeline mutations. Reconnect path re-fetches. |
| `BroadcastPipeline` | Each stage renders from its derived view; urgent badge appears; history collapsed by default. |
| Drag-and-drop | Dropping within a stage issues reorder POST with the new id order; optimistic UI rolls back on 400. |

## Rollout: three PRs

### PR 1 — `OrderedItemStore` + tts_player swap

Pure refactor. No user-visible change. No new events, no new endpoints.

- New `src/shared/ordered_item_store.py` + test.
- `tts_player.py`: replace `queue.Queue` (both) with `OrderedItemStore`.
- `session.py::get_tts_queue_snapshot`: adapt to new API, same payload shape.

**Acceptance:** all existing tests pass; manual e2e (start → LLM generates → TTS plays) works with no audible artifacts.

### PR 2 — `stage` field + `tts_synthesized` event + snapshot endpoint

Data plumbing only. UI still uses the old three-component layout via an adapter.

- `TtsItem` / `PcmItem` gain `stage` and `urgent` fields.
- `on_synthesized` callback wired in `tts_player`; `session.py` publishes `tts_synthesized`.
- `tts_queued` payload widened with `stage` + `urgent`.
- `get_tts_queue_snapshot` includes new fields.
- New `GET /live/tts/queue/snapshot`.
- `useLiveStream` refactored to the single `pipeline` array; the three existing components receive derived views via a thin adapter.

**Acceptance:** pytest + vitest + typecheck green; DevTools shows `tts_synthesized` events; behavior unchanged.

### PR 3 — mutation endpoints + `BroadcastPipeline`

Full user-visible refactor.

- `SessionManager.remove_tts` / `edit_tts` / `reorder_tts`.
- `DELETE` / `PATCH` / `POST reorder` endpoints.
- `tts_removed` / `tts_edited` / `tts_reordered` SSE events.
- `@dnd-kit/core` + `@dnd-kit/sortable` installed in `apps/web`.
- `BroadcastPipeline` and helpers created; old three components deleted; `live/page.tsx` middle column replaced.

**Acceptance:** pytest + vitest + typecheck green; manual e2e covers delete/edit/reorder in both stages + attempt to edit a playing item (blocked); motion transitions smooth.

## Open Questions

None at design time. Defer to implementation plan.

---

**Next step:** implementation plan via `superpowers:writing-plans`.
