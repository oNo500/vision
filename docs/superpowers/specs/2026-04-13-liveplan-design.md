# LivePlan System Design

## Goal

Build a pre-live content management system that stores structured plans (product info, persona, script) in the database, provides CRUD UI in a standalone page, and enriches DirectorAgent context at session start.

## Architecture

### Data Model

Stored as JSON in a single `live_plans` table:

```
LivePlan
├── id: str (UUID)
├── name: str
├── created_at: datetime
├── updated_at: datetime
├── product: {
│     name: str
│     description: str
│     price: str
│     highlights: str[]
│     faq: { question: str, answer: str }[]
│   }
├── persona: {
│     name: str
│     style: str
│     catchphrases: str[]
│     forbidden_words: str[]
│   }
└── script: {
      segments: [{
        id: str
        text: str
        duration: int (seconds)
        must_say: bool
        keywords: str[]
      }]
    }
```

A `LivePlan` is a reusable template. Users create them before going live, edit after each session to capture what worked, and load one per session.

### API Endpoints

All under `/live/plans`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/live/plans` | List all plans (id, name, updated_at only) |
| POST | `/live/plans` | Create plan |
| GET | `/live/plans/{id}` | Get full plan |
| PUT | `/live/plans/{id}` | Update plan |
| DELETE | `/live/plans/{id}` | Delete plan |
| POST | `/live/plans/{id}/load` | Load plan into active session |
| GET | `/live/plans/active` | Get currently loaded plan |

`SessionManager` gains an `active_plan_id: str | None` field. `/live/session/start` accepts an optional `plan_id` parameter — if provided, loads the plan before starting.

### Database

New `live_plans` table in the existing SQLite database (`vision.db`):

```sql
CREATE TABLE live_plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    data TEXT NOT NULL,   -- JSON blob of the full plan
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

`Database` class gains `create_plan`, `list_plans`, `get_plan`, `update_plan`, `delete_plan` methods.

### DirectorAgent Context Integration

When a plan is loaded, `SessionManager.start()` derives context from the plan instead of reading flat files:

- `knowledge_ctx` = assembled from `product.description + highlights + faq` (replaces `product_path` file read)
- `persona_ctx` = assembled from `persona.name + style + catchphrases + forbidden_words` (new)
- `ScriptRunner` receives `script.segments` directly (replaces `script_path` file read)

`build_director_prompt()` gains a `persona_ctx` parameter injected into the system prompt prefix.
The system prompt appends: `"禁用词：{forbidden_words}"` when forbidden_words is non-empty.

Fallback: if no plan is loaded, `SessionManager` falls back to `script_path` / `product_path` file reads (existing behavior preserved for backwards compatibility during transition).

---

## UI

### 方案库 Page (`/live/plans`)

Standalone page at the same level as `/live`. Shows a table of plans with actions.

```
[+ 新建方案]

┌────────────────────────────────────────────┐
│  方案名称       更新时间        操作          │
├────────────────────────────────────────────┤
│  夏季护肤套装   2026-04-10    编辑  加载  删除 │
│  新品发布专场   2026-04-08    编辑  加载  删除 │
└────────────────────────────────────────────┘
```

「编辑」navigates to `/live/plans/{id}`. 「加载」calls `POST /live/plans/{id}/load` and navigates to `/live`.

### 方案编辑 Page (`/live/plans/{id}`)

Three-tab layout:

```
┌──────────┬────────────────────────────────────┐
│ > 产品信息 │  产品名称 ________________         │
│   人设风格 │  描述     ________________         │
│   直播脚本 │  价格     ________________         │
│           │  亮点     [+ 添加]                  │
│           │  FAQ      [+ 添加]                  │
└──────────┴────────────────────────────────────┘
```

人设风格 tab: name, style (textarea), catchphrases (tag input), forbidden_words (tag input).

直播脚本 tab: ordered list of segments. Each segment shows text, duration, must_say toggle, keywords. Drag to reorder. Add/remove segments.

Bottom bar: `[保存]` `[保存并加载]`

### 控场 Plan Panel (`/live`)

Collapsible panel at top of 直播控场 page. Collapsed by default after initial load.

```
▶ 当前方案：夏季护肤套装  [切换方案↗]
```

Expanded:

```
▼ 当前方案：夏季护肤套装  [切换方案↗]
  产品：xxx 护肤套装 · ¥299
  人设：温柔姐姐 · 专业亲切
  脚本：12 个段落，预计 45 分钟
```

「切换方案↗」links to `/live/plans`. No editing from 控场 — read-only.

---

## Error Handling

- `POST /live/plans/{id}/load` while session is running: returns 409 with message "Session is running, stop it before loading a new plan"
- `DELETE /live/plans/{id}` when plan is currently active: returns 409
- Plan not found: 404
- Invalid plan data (missing required fields): 422

---

## Out of Scope

- Script branching / free mode (roadmap)
- Plan versioning / history
- Multiple active plans / A-B testing
- Plan sharing between users
- TTS decoupling / OutputRouter (separate design)
