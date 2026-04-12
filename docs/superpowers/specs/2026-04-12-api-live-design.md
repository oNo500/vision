# API + Live Routes Design

**Date:** 2026-04-12
**Status:** Approved

## Overview

Add a FastAPI service (`src/api/`) that exposes `src/live/` capabilities over HTTP to `apps/api-web` (Next.js dashboard). The API is internal-only — not publicly exposed. A single live Agent instance runs per process; the architecture does not preclude future multi-session support.

---

## Architecture

```
src/
├── api/
│   ├── __init__.py
│   ├── main.py        # FastAPI app, lifespan, router registration
│   ├── settings.py    # pydantic-settings, reads .env
│   └── deps.py        # FastAPI dependency injection helpers
├── live/
│   ├── ...            # existing code, untouched
│   └── routes.py      # live domain FastAPI router (new)
└── shared/
    ├── __init__.py
    ├── event_bus.py   # in-memory pub/sub: Agent threads → SSE coroutines
    └── db.py          # SQLite connection + schema bootstrap
```

**Data flow:**

1. `POST /live/start` → `SessionManager` assembles Agent components, starts threads
2. Agent components (`TTSPlayer`, `Orchestrator`, `DirectorAgent`) publish events to `EventBus`
3. `GET /live/stream` subscribes to `EventBus`, streams events as SSE to the browser
4. `EventBus` also fans out to `db.py` for SQLite persistence

---

## Components

### `src/shared/event_bus.py`

In-memory fan-out bus bridging sync Agent threads and async SSE handlers.

- `publish(event: dict)` — callable from any thread (sync-safe via `loop.call_soon_threadsafe`)
- `subscribe() -> asyncio.Queue` — returns a per-connection queue; SSE handler drains it
- `unsubscribe(queue)` — called on client disconnect
- No external dependencies (pure stdlib)

### `src/shared/db.py`

SQLite via `aiosqlite`. Two tables, bootstrapped on startup:

```sql
CREATE TABLE IF NOT EXISTS tts_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content       TEXT NOT NULL,
    speech_prompt TEXT,
    source        TEXT,   -- "script" | "interaction" | "knowledge" | "rule"
    ts            REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS event_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    type    TEXT NOT NULL,  -- "danmaku" | "gift" | "enter" | "director"
    payload TEXT NOT NULL,  -- JSON blob
    ts      REAL NOT NULL
);
```

### `src/api/main.py`

FastAPI app with `lifespan` that:
1. Bootstraps SQLite tables (`db.init()`)
2. Instantiates `EventBus` and `SessionManager`, stored on `app.state`
3. Registers `live_router` under `/live`

### `src/live/routes.py`

FastAPI router for the live domain. Depends on `SessionManager` and `EventBus` via `deps.py`.

### `SessionManager`

Owns the single Agent instance. Responsible for:
- Assembling all components (`ScriptRunner`, `Orchestrator`, `DirectorAgent`, `TTSPlayer`, event collector)
- Wiring `EventBus.publish` into each component as a callback
- Starting / stopping background threads
- Exposing a `get_state() -> dict` snapshot

Lives in `src/live/session.py`.

---

## HTTP Interface

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/live/start` | Start Agent. Body: `{script, product, mock, project}` |
| `POST` | `/live/stop` | Stop Agent |
| `GET` | `/live/state` | State snapshot: segment progress, queue depth, running status |
| `POST` | `/live/inject` | Queue a manual TTS utterance. Body: `{content, speech_prompt?}` |
| `GET` | `/live/stream` | SSE stream of real-time events |
| `GET` | `/live/history` | SQLite history. Query params: `limit`, `type` |
| `GET` | `/health` | Health check |

### SSE Event Schema

All events share the envelope:

```json
{ "type": "<event_type>", "ts": 1234567890.123, ...fields }
```

| `type` | Additional fields |
|--------|-------------------|
| `tts_output` | `content`, `speech_prompt`, `source` |
| `danmaku` | `user`, `text` |
| `gift` | `user`, `gift`, `value` |
| `enter` | `user`, `is_follower` |
| `director` | `content`, `speech_prompt`, `source`, `reason` |
| `script` | `segment_id`, `remaining_seconds` |
| `agent` | `status` (`"started"` \| `"stopped"` \| `"error"`) |

---

## Data Layer

SQLite file at path configured via `VISION_DB_PATH` env var (default: `vision.db` in project root).

`GET /live/history` supports:
- `?limit=100` (default 100, max 500)
- `?type=tts_output` — filter to `tts_log` only
- `?type=events` — filter to `event_log` only
- No type param — returns both, merged and sorted by `ts` descending

---

## Wiring Agent Components to EventBus

The existing Agent components use callbacks / queues. The integration strategy minimises changes to existing code:

- **TTSPlayer** — wrap `speak_fn`: after each utterance, call `event_bus.publish(tts_output)` and `db.log_tts()`
- **Orchestrator** — wrap `_enqueue_tts`: publish `tts_output` (rule-triggered) events
- **DirectorAgent** — wrap `_fire`: publish `director` events after each LLM output
- **Event collectors** — wrap `event_queue.put`: publish `danmaku` / `gift` / `enter` events

All wrappers live in `SessionManager`, not in the original modules — zero changes to `src/live/` business logic.

---

## Error Handling

- `POST /live/start` when already running → `409 Conflict`
- `POST /live/stop` when not running → `400 Bad Request`
- `POST /live/inject` when not running → `400 Bad Request`
- Agent thread crash → publishes `{"type": "agent", "status": "error", "detail": "..."}` via EventBus, `SessionManager` marks state as stopped

---

## Testing

- `src/shared/event_bus.py` — unit tests: publish/subscribe, multi-subscriber fan-out, unsubscribe on disconnect
- `src/shared/db.py` — unit tests with in-memory SQLite (`:memory:`)
- `src/live/routes.py` — FastAPI `TestClient` tests: each endpoint, SSE event sequence for start→inject→stop
- `SessionManager` — unit tests with mock Agent components (no real threads)
- No changes needed to existing `tests/live/` suite

---

## Dependencies to Add

```toml
# pyproject.toml
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic-settings>=2.0
aiosqlite>=0.20
```

---

## Startup Command

```bash
uv run uvicorn src.api.main:app --reload --port 8000
```
