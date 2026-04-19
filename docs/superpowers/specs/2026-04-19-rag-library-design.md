# RAG Library Decoupling Design

**Date**: 2026-04-19
**Status**: Approved

## Overview

Decouple RAG (talk-point retrieval) from Live Plans. A `RagLibrary` is an
independent entity that can be shared across plans and populated from video
transcripts or manual uploads. Plans reference one or more libraries by ID.

Embedding backend switches from sentence-transformers to Vertex AI
`text-multilingual-embedding-002`, removing the torch/sentence-transformers
dependency. Existing `.rag/` data is discarded (early development, no migration).

---

## 1. Data Model

### RagLibrary

```python
class RagLibrary(BaseModel):
    id: str       # user-defined slug, e.g. "dong-yuhui"
    name: str     # display name, e.g. "董宇辉"
    created_at: str
```

Stored in a new `rag_libraries` SQLite table managed by `vision-shared`
`Database`. File content lives at `data/talk_points/<lib_id>/` using the
existing four-category layout:

```
data/talk_points/<lib_id>/
├── scripts/
├── competitor_clips/
├── product_manual/
└── qa_log/
```

ChromaDB index at `.rag/<lib_id>/`, collection name `talkpoints_<lib_id>`.

### Plan → Library Association

`live_plans` table gains a `rag_library_ids` JSON column (default `[]`).
A plan may reference multiple libraries.

### Multi-library Query

`TalkPointRAG` accepts multiple ChromaDB collections. On `query()`, it
queries all collections concurrently and merges results by similarity score,
returning the global top-k above the threshold.

---

## 2. Backend API

All new routes under `/api/intelligence/rag-libraries` are protected by the
existing API Key middleware.

### Library CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/intelligence/rag-libraries/` | List all libraries |
| POST | `/api/intelligence/rag-libraries/` | Create library `{id, name}` |
| DELETE | `/api/intelligence/rag-libraries/{lib_id}` | Delete library + data/ + .rag/ |
| GET | `/api/intelligence/rag-libraries/{lib_id}/status` | File list + index state |
| POST | `/api/intelligence/rag-libraries/{lib_id}/files` | Upload file |
| DELETE | `/api/intelligence/rag-libraries/{lib_id}/files/{cat}/{fn}` | Delete file |
| POST | `/api/intelligence/rag-libraries/{lib_id}/rebuild` | Trigger index rebuild |
| GET | `/api/intelligence/rag-libraries/{lib_id}/rebuild/status` | Build status |
| POST | `/api/intelligence/rag-libraries/{lib_id}/import-transcript` | Import from transcript |

### import-transcript

```
POST /api/intelligence/rag-libraries/{lib_id}/import-transcript
Body: { "video_id": "BV1f64y1V7f2" }
```

Reads completed pipeline output from `output/transcripts/<video_id>/` and
copies into the library (idempotent, overwrites on re-import):

- `transcript.md` → `competitor_clips/<video_id>.md`
- `summary.md` → `scripts/<video_id>_summary.md`

Does **not** auto-trigger rebuild. Returns `{ "imported": ["competitor_clips/...", "scripts/..."] }`.

Fails with 404 if `output/transcripts/<video_id>/` does not exist or pipeline
has not completed (no `transcript.md`).

### Plan Library Association

```
PUT /live/plans/{plan_id}/rag-libraries
Body: { "library_ids": ["dong-yuhui", "li-jiaqi"] }
```

Replaces the full association list. Returns the updated plan.

---

## 3. Pages

### New top-level page: `/libraries`

Sidebar gets a new "素材库" entry.

**`/libraries`** — library list
- Cards showing: name, file count, chunk count, dirty indicator
- "新建素材库" button (form: id slug + display name)

**`/libraries/[id]`** — library detail
- Header: library name + delete button
- Tab 1 「文件」: existing `FileList` + `UploadDropzone` (reused as-is)
- Tab 2 「从转录导入」: list of completed videos from `output/transcripts/`
  - Each row: title, duration, source, import status (imported / not imported)
  - "导入" button → calls `import-transcript`, row updates to "已导入"
- Bottom: index status card + rebuild button

### Modified: `/plans/[id]` RAG tab

Renamed to "关联素材库". Replaces file management UI with:
- Multi-select list of all existing libraries
- Toggle saves via `PUT /live/plans/{plan_id}/rag-libraries`
- Shows chunk count and dirty state per library for reference

File management moves entirely to `/libraries/[id]`.

---

## 4. Embedding: Vertex AI

New module `vision_live/embedder.py`:

```python
def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via Vertex AI text-multilingual-embedding-002."""
    ...
```

- `rag_cli.py` and `rag.py` both import from `embedder.py`
- Tests inject a fake embedder (fixed-length zero vectors)
- `sentence-transformers` removed from `vision-live` dependencies
- Existing `.rag/` directories deleted; all libraries rebuilt after deploy

---

## 5. Testing

| Layer | File | What it covers |
|-------|------|---------------|
| unit | `embedder_test.py` | fake embedder injection, no Vertex AI call |
| unit | `rag_test.py` | multi-collection merge, score filtering (existing pattern) |
| unit | `rag_cli_test.py` | scan/diff/chunk with mock embedder |
| integration | `rag_library_routes_test.py` | CRUD, import-transcript, rebuild trigger |
| integration | `live_routes_test.py` | plan rag-libraries association endpoint |
| frontend | `use-rag-library.test.ts` | hook unit tests for new library hooks |

---

## Out of Scope

- `style.json` → `style_summary.md` pipeline output (separate task)
- Video transcript listing API (reuses existing `video_asr_routes` job/video endpoints)
