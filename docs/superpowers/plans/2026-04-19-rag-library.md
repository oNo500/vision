# RAG Library Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple RAG libraries from Live Plans, switch embedding to Vertex AI, and add a `/libraries` management page.

**Architecture:** `RagLibrary` is an independent SQLite entity; plans store a `rag_library_ids` JSON list. A new `embedder.py` module wraps Vertex AI embedding, replacing sentence-transformers. New FastAPI routes under `/api/intelligence/rag-libraries` handle CRUD, file management, import-from-transcript, and rebuild. A new `/libraries` Next.js page provides library management; the plan RAG tab is replaced with a library selector.

**Tech Stack:** Python 3.13, FastAPI, aiosqlite, ChromaDB, Vertex AI `text-multilingual-embedding-002`, Next.js 15 App Router, React, TypeScript

---

## File Map

### New files
- `python-packages/live/src/vision_live/embedder.py` — Vertex AI embed function + Protocol
- `python-packages/live/src/vision_live/embedder_test.py` — unit tests with fake embedder
- `python-packages/live/src/vision_live/rag_library_store.py` — SQLite CRUD for RagLibrary
- `python-packages/live/src/vision_live/rag_library_store_test.py`
- `python-packages/api/src/vision_api/rag_library_routes.py` — FastAPI routes for library management
- `python-packages/api/src/vision_api/rag_library_routes_test.py`
- `apps/web/src/features/live/hooks/use-rag-libraries.ts` — React hook for library list/CRUD
- `apps/web/src/features/live/hooks/use-rag-libraries.test.ts`
- `apps/web/src/features/live/hooks/use-rag-library.ts` — React hook for single library detail
- `apps/web/src/features/live/hooks/use-rag-library.test.ts`
- `apps/web/src/app/(dashboard)/libraries/page.tsx` — library list page
- `apps/web/src/app/(dashboard)/libraries/[id]/page.tsx` — library detail page
- `apps/web/src/features/live/components/rag-library/library-list.tsx`
- `apps/web/src/features/live/components/rag-library/library-detail.tsx`
- `apps/web/src/features/live/components/rag-library/import-transcript-tab.tsx`
- `apps/web/src/features/live/components/plan-rag-libraries.tsx` — plan library selector

### Modified files
- `python-packages/shared/src/vision_shared/db.py` — add `rag_libraries` table + `rag_library_ids` column migration
- `python-packages/shared/src/vision_shared/db_test.py` — add schema migration tests
- `python-packages/live/src/vision_live/rag_cli.py` — replace SentenceTransformer with embedder.py
- `python-packages/live/src/vision_live/rag.py` — replace SentenceTransformer with embedder.py; support multi-collection
- `python-packages/live/src/vision_live/rag_test.py` — add multi-collection merge test
- `python-packages/live/src/vision_live/plan_store.py` — add `rag_library_ids` field
- `python-packages/live/src/vision_live/plan_store_test.py` — add rag_library_ids tests  (currently `plan_store_test.py` does not exist — create it)
- `python-packages/api/src/vision_api/main.py` — register new router + init RagLibraryStore
- `python-packages/api/src/vision_api/deps.py` — add `get_rag_library_store`
- `python-packages/live/src/vision_live/plan_routes.py` — add `PUT /{plan_id}/rag-libraries`
- `apps/web/src/config/app-paths.ts` — add `libraries` paths
- `apps/web/src/components/app-sidebar.tsx` — add 素材库 nav item
- `apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx` — replace RagPanel with PlanRagLibraries

---

## Task 1: Vertex AI Embedder Module

**Files:**
- Create: `python-packages/live/src/vision_live/embedder.py`
- Create: `python-packages/live/src/vision_live/embedder_test.py`

- [ ] **Step 1: Write failing test**

```python
# python-packages/live/src/vision_live/embedder_test.py
"""Tests for embedder — uses a fake to avoid Vertex AI calls."""
from __future__ import annotations

from vision_live.embedder import Embedder, FakeEmbedder


def test_fake_embedder_returns_fixed_vectors():
    emb = FakeEmbedder(dim=4)
    vecs = emb.embed(["hello", "world"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 4
    assert all(v == 0.0 for v in vecs[0])


def test_fake_embedder_single_text():
    emb = FakeEmbedder(dim=8)
    vecs = emb.embed(["one text"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 8
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/xiu/code/vision
uv run pytest python-packages/live/src/vision_live/embedder_test.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement embedder.py**

```python
# python-packages/live/src/vision_live/embedder.py
"""Embedding abstraction — production uses Vertex AI, tests use FakeEmbedder."""
from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

_MODEL = "text-multilingual-embedding-002"
_BATCH_SIZE = 250  # Vertex AI limit per request


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Zero-vector embedder for tests. Never calls any external service."""

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]


class VertexEmbedder:
    """Calls Vertex AI text-multilingual-embedding-002."""

    def __init__(
        self,
        project: str | None = None,
        location: str = "us-central1",
        model: str = _MODEL,
    ) -> None:
        self._project = project
        self._location = location
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google import genai
        from google.genai import types as gtypes

        client = genai.Client(vertx_ai_mode=True, project=self._project, location=self._location)
        result: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = client.models.embed_content(
                model=self._model,
                contents=batch,
                config=gtypes.EmbedContentConfig(output_dimensionality=768),
            )
            for emb in response.embeddings:
                result.append(emb.values)
        return result


def get_default_embedder(
    project: str | None = None,
    location: str = "us-central1",
) -> VertexEmbedder:
    return VertexEmbedder(project=project, location=location)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest python-packages/live/src/vision_live/embedder_test.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add python-packages/live/src/vision_live/embedder.py python-packages/live/src/vision_live/embedder_test.py
git commit -m "feat(rag): add Vertex AI embedder module with FakeEmbedder"
```

---

## Task 2: Wire embedder into rag_cli and rag.py

**Files:**
- Modify: `python-packages/live/src/vision_live/rag_cli.py`
- Modify: `python-packages/live/src/vision_live/rag.py`
- Modify: `python-packages/live/src/vision_live/rag_test.py`

- [ ] **Step 1: Write failing test for multi-collection merge in rag.py**

Add to `python-packages/live/src/vision_live/rag_test.py`:

```python
# Add this test alongside existing tests in rag_test.py
def test_multi_collection_merge_deduplicates_by_score():
    """TalkPointRAG with two collections merges and sorts by similarity."""
    from vision_live.rag import TalkPointRAG
    from vision_live.embedder import FakeEmbedder

    class FakeCollection:
        def __init__(self, doc: str, distance: float) -> None:
            self._doc = doc
            self._distance = distance

        def query(self, query_embeddings, n_results):
            return {
                "documents": [[self._doc]],
                "metadatas": [[{"id": self._doc, "source": "src", "category": "scripts", "chunk_index": 0}]],
                "distances": [[self._distance]],
            }

    emb = FakeEmbedder()
    rag = TalkPointRAG(
        collections=[FakeCollection("a", 0.1), FakeCollection("b", 0.3)],
        embedder=emb,
        min_score=0.5,
    )
    results = rag.query("goal", [], k=5)
    # distance 0.1 → similarity 0.9; distance 0.3 → similarity 0.7; both above 0.5
    assert len(results) == 2
    assert results[0].text == "a"  # higher similarity first
    assert results[1].text == "b"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest python-packages/live/src/vision_live/rag_test.py::test_multi_collection_merge_deduplicates_by_score -v
```
Expected: FAIL — `TalkPointRAG` doesn't accept `collections` yet

- [ ] **Step 3: Update rag.py to support multiple collections**

Replace the `TalkPointRAG` class in `python-packages/live/src/vision_live/rag.py`:

```python
"""RAG retrieval for DirectorAgent — TalkPointRAG queries ChromaDB collections."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vision_live.embedder import Embedder, FakeEmbedder, get_default_embedder

logger = logging.getLogger(__name__)

_DEFAULT_MIN_SCORE = 0.5
_DEFAULT_K = 5


@dataclass
class TalkPoint:
    id: str
    text: str
    source: str
    category: str
    chunk_index: int


def _build_query(segment_goal: str, recent_danmaku: list[str]) -> str:
    danmaku_tail = " ".join(recent_danmaku[-3:])
    return f"{segment_goal} {danmaku_tail}".strip()


class TalkPointRAG:
    """Semantic retrieval over one or more ChromaDB collections.

    Args:
        collections: list of ChromaDB Collection objects.
        embedder: any object with embed(texts) -> list[list[float]].
        min_score: cosine similarity floor.
    """

    def __init__(
        self,
        collections: list,
        embedder: Embedder,
        min_score: float = _DEFAULT_MIN_SCORE,
    ) -> None:
        self._collections = collections
        self._embedder = embedder
        self._min_score = min_score

    def query(
        self,
        segment_goal: str,
        recent_danmaku: list[str],
        k: int = _DEFAULT_K,
    ) -> list[TalkPoint]:
        query_text = _build_query(segment_goal, recent_danmaku)
        embedding = self._embedder.embed([query_text])[0]

        candidates: list[tuple[float, TalkPoint]] = []
        for collection in self._collections:
            results = collection.query(
                query_embeddings=[list(embedding)],
                n_results=k,
            )
            docs = _first(results.get("documents"))
            metas = _first(results.get("metadatas"))
            distances = _first(results.get("distances"))
            for doc, meta, dist in zip(docs, metas, distances, strict=True):
                similarity = 1.0 - float(dist)
                if similarity < self._min_score:
                    continue
                candidates.append((similarity, TalkPoint(
                    id=str(meta.get("id", "")),
                    text=doc,
                    source=str(meta.get("source", "")),
                    category=str(meta.get("category", "")),
                    chunk_index=int(meta.get("chunk_index", 0)),
                )))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [tp for _, tp in candidates[:k]]


def _first(maybe_nested) -> list:
    if not maybe_nested:
        return []
    if isinstance(maybe_nested, list) and maybe_nested and isinstance(maybe_nested[0], list):
        return maybe_nested[0]
    return list(maybe_nested)


def load_rag_for_libraries(
    library_ids: list[str],
    rag_root: str | Path = ".rag",
    project: str | None = None,
    location: str = "us-central1",
) -> TalkPointRAG | None:
    """Open pre-built indexes for given libraries; return None if none found."""
    import chromadb

    rag_root = Path(rag_root)
    collections = []
    for lib_id in library_ids:
        path = rag_root / lib_id
        db_file = path / "chroma.sqlite3"
        if not db_file.exists():
            logger.info("RAG: no index at %s, skipping", path)
            continue
        try:
            client = chromadb.PersistentClient(path=str(path))
            collection = client.get_collection(f"talkpoints_{lib_id}")
            collections.append(collection)
        except Exception as e:
            logger.warning("RAG: collection for %s not found: %s", lib_id, e)

    if not collections:
        return None

    embedder = get_default_embedder(project=project, location=location)
    return TalkPointRAG(collections=collections, embedder=embedder)
```

- [ ] **Step 4: Update rag_cli.py to use embedder.py**

In `python-packages/live/src/vision_live/rag_cli.py`, replace the `SentenceTransformer` usage in `cmd_build`:

Find these lines:
```python
    import chromadb
    from sentence_transformers import SentenceTransformer
    ...
    embedder = SentenceTransformer("BAAI/bge-base-zh-v1.5")
    ...
    embeddings = embedder.encode(chunks, normalize_embeddings=True)
    ...
    embeddings=[e.tolist() for e in embeddings],
```

Replace with:
```python
    import chromadb
    from vision_live.embedder import get_default_embedder
    ...
    embedder = get_default_embedder()
    ...
    embeddings = embedder.embed(chunks)
    ...
    embeddings=embeddings,
```

Also remove the `from sentence_transformers import SentenceTransformer` line from `load_rag_for_plan` in `rag.py` (the old function is replaced above — delete the entire old `load_rag_for_plan` function if it remains).

- [ ] **Step 5: Delete stale .rag/ data**

```bash
rm -rf /Users/xiu/code/vision/.rag
```

- [ ] **Step 6: Run rag tests**

```bash
uv run pytest python-packages/live/src/vision_live/rag_test.py python-packages/live/src/vision_live/rag_cli_test.py -v
```
Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add python-packages/live/src/vision_live/rag.py python-packages/live/src/vision_live/rag_cli.py python-packages/live/src/vision_live/rag_test.py
git commit -m "feat(rag): switch embedding to Vertex AI, support multi-collection query"
```

---

## Task 3: RagLibrary SQLite store

**Files:**
- Modify: `python-packages/shared/src/vision_shared/db.py`
- Modify: `python-packages/shared/src/vision_shared/db_test.py`
- Create: `python-packages/live/src/vision_live/rag_library_store.py`
- Create: `python-packages/live/src/vision_live/rag_library_store_test.py`

- [ ] **Step 1: Write failing test for RagLibraryStore**

```python
# python-packages/live/src/vision_live/rag_library_store_test.py
"""Tests for RagLibraryStore CRUD."""
from __future__ import annotations

import pytest
import aiosqlite


@pytest.fixture
async def conn(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as c:
        await c.executescript("""
            CREATE TABLE IF NOT EXISTS rag_libraries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        await c.commit()
        yield c


async def test_create_and_list(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    lib = await store.create("dong-yuhui", "董宇辉")
    assert lib["id"] == "dong-yuhui"
    assert lib["name"] == "董宇辉"
    libs = await store.list_all()
    assert len(libs) == 1
    assert libs[0]["id"] == "dong-yuhui"


async def test_get_existing(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    await store.create("lib-a", "Library A")
    result = await store.get("lib-a")
    assert result is not None
    assert result["name"] == "Library A"


async def test_get_missing_returns_none(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    result = await store.get("nonexistent")
    assert result is None


async def test_delete(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    await store.create("to-delete", "Delete Me")
    await store.delete("to-delete")
    assert await store.get("to-delete") is None


async def test_create_duplicate_raises(conn):
    from vision_live.rag_library_store import RagLibraryStore
    store = RagLibraryStore(conn)
    await store.create("dup", "First")
    with pytest.raises(ValueError, match="already exists"):
        await store.create("dup", "Second")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest python-packages/live/src/vision_live/rag_library_store_test.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Add rag_libraries table to db.py**

In `python-packages/shared/src/vision_shared/db.py`, add to `_SCHEMA`:

```python
_SCHEMA = """
CREATE TABLE IF NOT EXISTS tts_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content       TEXT NOT NULL,
    speech_prompt TEXT,
    source        TEXT,
    ts            REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS event_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    type    TEXT NOT NULL,
    payload TEXT NOT NULL,
    ts      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS live_plans (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    data       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_libraries (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""
```

- [ ] **Step 4: Implement RagLibraryStore**

```python
# python-packages/live/src/vision_live/rag_library_store.py
"""Async CRUD for RagLibrary objects in SQLite."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RagLibraryStore:
    """Thin async CRUD wrapper around the rag_libraries table."""

    def __init__(self, conn: "aiosqlite.Connection") -> None:
        self._conn = conn

    async def create(self, lib_id: str, name: str) -> dict:
        existing = await self.get(lib_id)
        if existing is not None:
            raise ValueError(f"Library '{lib_id}' already exists")
        now = _now_iso()
        await self._conn.execute(
            "INSERT INTO rag_libraries (id, name, created_at) VALUES (?, ?, ?)",
            (lib_id, name, now),
        )
        await self._conn.commit()
        return {"id": lib_id, "name": name, "created_at": now}

    async def list_all(self) -> list[dict]:
        rows = []
        async with self._conn.execute(
            "SELECT id, name, created_at FROM rag_libraries ORDER BY created_at DESC"
        ) as cur:
            async for row in cur:
                rows.append({"id": row[0], "name": row[1], "created_at": row[2]})
        return rows

    async def get(self, lib_id: str) -> dict | None:
        async with self._conn.execute(
            "SELECT id, name, created_at FROM rag_libraries WHERE id = ?", (lib_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {"id": row[0], "name": row[1], "created_at": row[2]}

    async def delete(self, lib_id: str) -> None:
        await self._conn.execute("DELETE FROM rag_libraries WHERE id = ?", (lib_id,))
        await self._conn.commit()
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest python-packages/live/src/vision_live/rag_library_store_test.py -v
```
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add python-packages/shared/src/vision_shared/db.py python-packages/live/src/vision_live/rag_library_store.py python-packages/live/src/vision_live/rag_library_store_test.py
git commit -m "feat(rag): add RagLibraryStore and rag_libraries table"
```

---

## Task 4: Plan rag_library_ids field

**Files:**
- Modify: `python-packages/live/src/vision_live/plan_store.py`
- Create: `python-packages/live/src/vision_live/plan_store_test.py`

- [ ] **Step 1: Write failing test**

```python
# python-packages/live/src/vision_live/plan_store_test.py
"""Tests for PlanStore — focuses on rag_library_ids field."""
from __future__ import annotations

import pytest
import aiosqlite


@pytest.fixture
async def conn(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as c:
        await c.executescript("""
            CREATE TABLE IF NOT EXISTS live_plans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        await c.commit()
        yield c


async def test_create_plan_has_empty_rag_library_ids(conn):
    from vision_live.plan_store import PlanStore
    store = PlanStore(conn)
    plan = await store.create({"name": "Test Plan"})
    assert plan["rag_library_ids"] == []


async def test_update_rag_library_ids(conn):
    from vision_live.plan_store import PlanStore
    store = PlanStore(conn)
    plan = await store.create({"name": "Test Plan"})
    updated = await store.update(plan["id"], {**plan, "rag_library_ids": ["dong-yuhui"]})
    assert updated["rag_library_ids"] == ["dong-yuhui"]


async def test_get_plan_preserves_rag_library_ids(conn):
    from vision_live.plan_store import PlanStore
    store = PlanStore(conn)
    plan = await store.create({"name": "Test Plan"})
    await store.update(plan["id"], {**plan, "rag_library_ids": ["lib-a", "lib-b"]})
    fetched = await store.get(plan["id"])
    assert fetched["rag_library_ids"] == ["lib-a", "lib-b"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest python-packages/live/src/vision_live/plan_store_test.py -v
```
Expected: FAIL — plan dict has no `rag_library_ids`

- [ ] **Step 3: Update plan_store.py**

In `python-packages/live/src/vision_live/plan_store.py`, update `create` and `update`:

In `create`, add `"rag_library_ids"` to the plan dict:
```python
    plan = {
        "id": plan_id,
        "name": data["name"],
        "created_at": now,
        "updated_at": now,
        "product": data.get("product", {}),
        "persona": data.get("persona", {}),
        "script": data.get("script", {"segments": []}),
        "rag_library_ids": data.get("rag_library_ids", []),
    }
```

In `update`, add `rag_library_ids` to the updated dict:
```python
    updated = {
        **existing,
        "name": data.get("name", existing["name"]),
        "updated_at": now,
        "product": data.get("product", existing["product"]),
        "persona": data.get("persona", existing["persona"]),
        "script": data.get("script", existing["script"]),
        "rag_library_ids": data.get("rag_library_ids", existing.get("rag_library_ids", [])),
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest python-packages/live/src/vision_live/plan_store_test.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add python-packages/live/src/vision_live/plan_store.py python-packages/live/src/vision_live/plan_store_test.py
git commit -m "feat(plan): add rag_library_ids field to LivePlan"
```

---

## Task 5: RAG Library FastAPI Routes

**Files:**
- Create: `python-packages/api/src/vision_api/rag_library_routes.py`
- Create: `python-packages/api/src/vision_api/rag_library_routes_test.py`
- Modify: `python-packages/api/src/vision_api/deps.py`
- Modify: `python-packages/api/src/vision_api/main.py`

- [ ] **Step 1: Write failing tests**

```python
# python-packages/api/src/vision_api/rag_library_routes_test.py
"""Integration tests for /api/intelligence/rag-libraries routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
async def app(tmp_path):
    import aiosqlite
    from vision_api.main import create_app
    from vision_live.rag_library_store import RagLibraryStore
    from vision_intelligence.video_asr.config import VideoAsrSettings

    application = create_app()
    db_path = tmp_path / "test.db"
    conn = await aiosqlite.connect(db_path)
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS rag_libraries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    await conn.commit()
    application.state.rag_library_store = RagLibraryStore(conn)
    settings = VideoAsrSettings()
    settings.output_root = str(tmp_path / "transcripts")
    application.state.video_asr_settings = settings
    application.state.rag_builds = {}
    yield application
    await conn.close()


@pytest.fixture
async def client(app):
    headers = {"X-API-Key": "test-key"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    ) as c:
        yield c


async def test_create_and_list_libraries(client):
    r = await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "dong-yuhui", "name": "董宇辉"},
    )
    assert r.status_code == 201
    assert r.json()["id"] == "dong-yuhui"

    r = await client.get("/api/intelligence/rag-libraries/")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_library(client, tmp_path):
    await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "to-del", "name": "Delete Me"},
    )
    r = await client.delete("/api/intelligence/rag-libraries/to-del")
    assert r.status_code == 204

    r = await client.get("/api/intelligence/rag-libraries/")
    assert r.json() == []


async def test_import_transcript_missing_video(client):
    r = await client.post(
        "/api/intelligence/rag-libraries/my-lib/import-transcript",
        json={"video_id": "nonexistent"},
    )
    assert r.status_code == 404


async def test_import_transcript_success(client, tmp_path):
    # Create library
    await client.post(
        "/api/intelligence/rag-libraries/",
        json={"id": "my-lib", "name": "My Lib"},
    )

    # Seed transcript output
    video_dir = tmp_path / "transcripts" / "vid123"
    video_dir.mkdir(parents=True)
    (video_dir / "transcript.md").write_text("# Transcript\nhello world", encoding="utf-8")
    (video_dir / "summary.md").write_text("# Summary\ngreat video", encoding="utf-8")

    r = await client.post(
        "/api/intelligence/rag-libraries/my-lib/import-transcript",
        json={"video_id": "vid123"},
    )
    assert r.status_code == 200
    imported = r.json()["imported"]
    assert "competitor_clips/vid123.md" in imported
    assert "scripts/vid123_summary.md" in imported
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest python-packages/api/src/vision_api/rag_library_routes_test.py -v
```
Expected: ImportError or routing errors

- [ ] **Step 3: Add get_rag_library_store to deps.py**

In `python-packages/api/src/vision_api/deps.py`, add:

```python
def get_rag_library_store(request: Request):
    return request.app.state.rag_library_store
```

- [ ] **Step 4: Implement rag_library_routes.py**

```python
# python-packages/api/src/vision_api/rag_library_routes.py
"""FastAPI routes for /api/intelligence/rag-libraries."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from vision_api.deps import get_rag_library_store
from vision_live import rag_cli
from vision_live.rag_library_store import RagLibraryStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence/rag-libraries")


class LibraryCreate(BaseModel):
    id: str
    name: str


class ImportTranscriptBody(BaseModel):
    video_id: str


def _build_state(app_state) -> dict:
    if not hasattr(app_state, "rag_builds"):
        app_state.rag_builds = {}
    return app_state.rag_builds


def _run_build_sync(request: Request, lib_id: str) -> None:
    import traceback
    from datetime import datetime, timezone
    state = _build_state(request.app.state)
    state[lib_id] = {"running": True, "last_build_time": None, "last_error": None}
    try:
        rag_cli.cmd_build(lib_id)
        state[lib_id] = {
            "running": False,
            "last_build_time": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        }
    except Exception as e:
        logger.exception("RAG build failed for library %s", lib_id)
        state[lib_id] = {
            "running": False,
            "last_build_time": state[lib_id].get("last_build_time"),
            "last_error": f"{e}\n{traceback.format_exc()}"[:1000],
        }


@router.get("/")
async def list_libraries(store: RagLibraryStore = Depends(get_rag_library_store)) -> list[dict]:
    return await store.list_all()


@router.post("/", status_code=201)
async def create_library(
    body: LibraryCreate,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    import re
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", body.id):
        raise HTTPException(status_code=400, detail="id must be lowercase alphanumeric with hyphens")
    try:
        return await store.create(body.id, body.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/{lib_id}", status_code=204)
async def delete_library(
    lib_id: str,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> Response:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")
    await store.delete(lib_id)
    data_dir = rag_cli.DATA_ROOT / lib_id
    rag_dir = rag_cli.INDEX_ROOT / lib_id
    if data_dir.exists():
        shutil.rmtree(data_dir)
    if rag_dir.exists():
        shutil.rmtree(rag_dir)
    return Response(status_code=204)


@router.get("/{lib_id}/status")
def get_status(lib_id: str) -> dict:
    return rag_cli.get_plan_status(lib_id)


@router.post("/{lib_id}/files", status_code=201)
async def upload_file(
    lib_id: str,
    category: str = Form(...),
    file: UploadFile = File(...),
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")
    if category not in rag_cli.KNOWN_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {rag_cli.KNOWN_CATEGORIES}")
    raw_name = file.filename or ""
    suffix = Path(raw_name).suffix.lower()
    if suffix not in rag_cli.ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"only {rag_cli.ALLOWED_SUFFIXES} allowed")
    import re
    safe_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5._-]", "_", Path(raw_name).name)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file exceeds 5MB limit")
    target_dir = rag_cli.DATA_ROOT / lib_id / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    overwritten = target.exists()
    target.write_bytes(content)
    return {"rel_path": f"{category}/{safe_name}", "category": category, "overwritten": overwritten}


@router.delete("/{lib_id}/files/{category}/{filename}", status_code=204)
async def delete_file(
    lib_id: str,
    category: str,
    filename: str,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> Response:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")
    if category not in rag_cli.KNOWN_CATEGORIES:
        raise HTTPException(status_code=400, detail="unknown category")
    import re
    safe_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5._-]", "_", Path(filename).name)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    target = rag_cli.DATA_ROOT / lib_id / category / safe_name
    try:
        target.unlink()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="file not found") from None
    return Response(status_code=204)


@router.post("/{lib_id}/import-transcript")
async def import_transcript(
    lib_id: str,
    body: ImportTranscriptBody,
    request: Request,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")

    settings = request.app.state.video_asr_settings
    video_dir = Path(settings.output_root) / body.video_id
    transcript_md = video_dir / "transcript.md"
    summary_md = video_dir / "summary.md"

    if not transcript_md.exists():
        raise HTTPException(status_code=404, detail=f"transcript for video '{body.video_id}' not found")

    imported: list[str] = []

    dest_clips = rag_cli.DATA_ROOT / lib_id / "competitor_clips"
    dest_clips.mkdir(parents=True, exist_ok=True)
    clip_target = dest_clips / f"{body.video_id}.md"
    clip_target.write_bytes(transcript_md.read_bytes())
    imported.append(f"competitor_clips/{body.video_id}.md")

    if summary_md.exists():
        dest_scripts = rag_cli.DATA_ROOT / lib_id / "scripts"
        dest_scripts.mkdir(parents=True, exist_ok=True)
        script_target = dest_scripts / f"{body.video_id}_summary.md"
        script_target.write_bytes(summary_md.read_bytes())
        imported.append(f"scripts/{body.video_id}_summary.md")

    return {"imported": imported, "video_id": body.video_id}


@router.post("/{lib_id}/rebuild", status_code=202)
def trigger_rebuild(
    lib_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    state = _build_state(request.app.state)
    if state.get(lib_id, {}).get("running"):
        raise HTTPException(status_code=409, detail="build already running")
    background_tasks.add_task(_run_build_sync, request, lib_id)
    return {"scheduled": True}


@router.get("/{lib_id}/rebuild/status")
def rebuild_status(lib_id: str, request: Request) -> dict:
    state = _build_state(request.app.state)
    return state.get(lib_id) or {"running": False, "last_build_time": None, "last_error": None}
```

- [ ] **Step 5: Register router and init store in main.py**

In `python-packages/api/src/vision_api/main.py`, add imports and wiring:

```python
# Add to imports at top:
from vision_api.rag_library_routes import router as rag_library_router
from vision_live.rag_library_store import RagLibraryStore
```

In the `lifespan` context manager, after `asr_storage.init_schema()`:
```python
        rag_lib_store = RagLibraryStore(app.state.db.conn)
        app.state.rag_library_store = rag_lib_store
```

After `app.include_router(video_asr_router)`:
```python
    app.include_router(rag_library_router)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest python-packages/api/src/vision_api/rag_library_routes_test.py -v
```
Expected: 4 PASSED

- [ ] **Step 7: Commit**

```bash
git add python-packages/api/src/vision_api/rag_library_routes.py python-packages/api/src/vision_api/rag_library_routes_test.py python-packages/api/src/vision_api/deps.py python-packages/api/src/vision_api/main.py
git commit -m "feat(api): add rag-libraries CRUD and import-transcript routes"
```

---

## Task 6: Plan rag-libraries association endpoint

**Files:**
- Modify: `python-packages/live/src/vision_live/plan_routes.py`
- Modify: `python-packages/api/src/vision_api/video_asr_routes_test.py` (add plan association test to existing live_routes_test.py)

- [ ] **Step 1: Write failing test**

Add to `python-packages/api/src/vision_api/live_routes_test.py`:

```python
async def test_put_plan_rag_libraries(client):
    # create a plan first
    r = await client.post("live/plans", json={"name": "Test"})
    assert r.status_code == 201
    plan_id = r.json()["id"]

    # associate libraries
    r = await client.put(
        f"live/plans/{plan_id}/rag-libraries",
        json={"library_ids": ["dong-yuhui", "li-jiaqi"]},
    )
    assert r.status_code == 200
    assert r.json()["rag_library_ids"] == ["dong-yuhui", "li-jiaqi"]


async def test_put_plan_rag_libraries_replaces(client):
    r = await client.post("live/plans", json={"name": "Test"})
    plan_id = r.json()["id"]
    await client.put(f"live/plans/{plan_id}/rag-libraries", json={"library_ids": ["a"]})
    r = await client.put(f"live/plans/{plan_id}/rag-libraries", json={"library_ids": ["b"]})
    assert r.json()["rag_library_ids"] == ["b"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest python-packages/api/src/vision_api/live_routes_test.py::test_put_plan_rag_libraries -v
```
Expected: 404 (route not found)

- [ ] **Step 3: Add endpoint to plan_routes.py**

In `python-packages/live/src/vision_live/plan_routes.py`, add after the existing routes:

```python
class RagLibrariesBody(BaseModel):
    library_ids: list[str]


@router.put("/{plan_id}/rag-libraries")
async def update_plan_rag_libraries(
    plan_id: str,
    body: RagLibrariesBody,
    store: PlanStore = Depends(get_plan_store),
) -> dict:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    updated = await store.update(plan_id, {**plan, "rag_library_ids": body.library_ids})
    return updated
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest python-packages/api/src/vision_api/live_routes_test.py -v
```
Expected: all PASSED (including new tests)

- [ ] **Step 5: Commit**

```bash
git add python-packages/live/src/vision_live/plan_routes.py python-packages/api/src/vision_api/live_routes_test.py
git commit -m "feat(plan): add PUT /{plan_id}/rag-libraries endpoint"
```

---

## Task 7: Frontend — hooks and app-paths

**Files:**
- Modify: `apps/web/src/config/app-paths.ts`
- Create: `apps/web/src/features/live/hooks/use-rag-libraries.ts`
- Create: `apps/web/src/features/live/hooks/use-rag-libraries.test.ts`
- Create: `apps/web/src/features/live/hooks/use-rag-library.ts`
- Create: `apps/web/src/features/live/hooks/use-rag-library.test.ts`

- [ ] **Step 1: Add library paths to app-paths.ts**

```typescript
// apps/web/src/config/app-paths.ts
export const appPaths = {
  home: {
    href: '/',
  },
  dashboard: {
    live: {
      href: '/live',
    },
    plans: {
      href: '/plans',
    },
    plan: (id: string) => ({
      href: `/plans/${id}`,
    }),
    planRag: (id: string) => ({
      href: `/plans/${id}/rag`,
    }),
    libraries: {
      href: '/libraries',
    },
    library: (id: string) => ({
      href: `/libraries/${id}`,
    }),
  },
}
```

- [ ] **Step 2: Write failing tests for use-rag-libraries**

```typescript
// apps/web/src/features/live/hooks/use-rag-libraries.test.ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRagLibraries } from './use-rag-libraries'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

function ok<T>(data: T) {
  return { ok: true as const, data, status: 200 }
}

describe('useRagLibraries', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches library list on mount', async () => {
    const libs = [{ id: 'dong-yuhui', name: '董宇辉', created_at: '2026-01-01T00:00:00Z' }]
    mockApiFetch.mockResolvedValueOnce(ok(libs))
    const { result } = renderHook(() => useRagLibraries())
    await waitFor(() => expect(result.current.libraries).toHaveLength(1))
    expect(result.current.libraries[0].id).toBe('dong-yuhui')
  })

  it('creates library and refetches', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok([]))
      .mockResolvedValueOnce(ok({ id: 'new-lib', name: 'New', created_at: '' }))
      .mockResolvedValueOnce(ok([{ id: 'new-lib', name: 'New', created_at: '' }]))
    const { result } = renderHook(() => useRagLibraries())
    await waitFor(() => expect(result.current.libraries).toEqual([]))
    await act(() => result.current.createLibrary('new-lib', 'New'))
    await waitFor(() => expect(result.current.libraries).toHaveLength(1))
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/xiu/code/vision && pnpm --filter web test --run 2>&1 | grep "use-rag-libraries"
```
Expected: test file not found or import error

- [ ] **Step 4: Implement use-rag-libraries.ts**

```typescript
// apps/web/src/features/live/hooks/use-rag-libraries.ts
'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from '@workspace/ui/components/sonner'
import { apiFetch } from '@/lib/api-fetch'

export type RagLibrary = {
  id: string
  name: string
  created_at: string
}

const BASE = 'api/intelligence/rag-libraries'

export function useRagLibraries() {
  const [libraries, setLibraries] = useState<RagLibrary[]>([])
  const [loading, setLoading] = useState(false)

  const refetch = useCallback(async () => {
    const res = await apiFetch<RagLibrary[]>(`${BASE}/`, { silent: true })
    if (res.ok) setLibraries(res.data)
  }, [])

  useEffect(() => { refetch() }, [refetch])

  const createLibrary = useCallback(async (id: string, name: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<RagLibrary>(`${BASE}/`, {
        method: 'POST',
        body: { id, name },
        fallbackError: '创建失败',
      })
      if (res.ok) {
        toast.success(`已创建素材库 ${name}`)
        await refetch()
      }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [refetch])

  const deleteLibrary = useCallback(async (id: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`${BASE}/${id}`, {
        method: 'DELETE',
        fallbackError: '删除失败',
      })
      if (res.ok) {
        toast.success('已删除素材库')
        await refetch()
      }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [refetch])

  return { libraries, loading, createLibrary, deleteLibrary, refetch }
}
```

- [ ] **Step 5: Write failing tests for use-rag-library**

```typescript
// apps/web/src/features/live/hooks/use-rag-library.test.ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRagLibrary } from './use-rag-library'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

function ok<T>(data: T) { return { ok: true as const, data, status: 200 } }

const emptyStatus = { indexed: false, dirty: false, chunk_count: 0, build_time: null, file_count: 0, sources: [] }
const idleBuild = { running: false, last_build_time: null, last_error: null }

describe('useRagLibrary', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches status and build status on mount', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
    const { result } = renderHook(() => useRagLibrary('dong-yuhui'))
    await waitFor(() => expect(result.current.status).not.toBeNull())
    expect(result.current.status).toEqual(emptyStatus)
  })

  it('importTranscript calls correct endpoint', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
      .mockResolvedValueOnce(ok({ imported: ['competitor_clips/vid.md'], video_id: 'vid' }))
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
    const { result } = renderHook(() => useRagLibrary('dong-yuhui'))
    await waitFor(() => expect(result.current.status).not.toBeNull())
    await act(() => result.current.importTranscript('vid'))
    expect(mockApiFetch).toHaveBeenCalledWith(
      'api/intelligence/rag-libraries/dong-yuhui/import-transcript',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
```

- [ ] **Step 6: Implement use-rag-library.ts**

```typescript
// apps/web/src/features/live/hooks/use-rag-library.ts
'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from '@workspace/ui/components/sonner'
import { apiFetch } from '@/lib/api-fetch'
import type { RagBuildStatus, RagCategory, RagStatus } from './use-rag'

const BASE = (libId: string) => `api/intelligence/rag-libraries/${libId}`
const BUILD_POLL_MS = 1500

export function useRagLibrary(libId: string) {
  const [status, setStatus] = useState<RagStatus | null>(null)
  const [buildStatus, setBuildStatus] = useState<RagBuildStatus>({
    running: false,
    last_build_time: null,
    last_error: null,
  })
  const [loading, setLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refetch = useCallback(async () => {
    const res = await apiFetch<RagStatus>(`${BASE(libId)}/status`, { silent: true })
    if (res.ok) setStatus(res.data)
  }, [libId])

  const refetchBuild = useCallback(async () => {
    const res = await apiFetch<RagBuildStatus>(`${BASE(libId)}/rebuild/status`, { silent: true })
    if (!res.ok) return null
    const next = res.data
    setBuildStatus(prev =>
      prev.running === next.running && prev.last_build_time === next.last_build_time && prev.last_error === next.last_error
        ? prev : next
    )
    return next
  }, [libId])

  useEffect(() => { Promise.all([refetch(), refetchBuild()]) }, [refetch, refetchBuild])

  useEffect(() => {
    if (!buildStatus.running) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return
    }
    pollRef.current = setInterval(async () => {
      const next = await refetchBuild()
      if (next && !next.running) {
        await refetch()
        if (next.last_error) toast.error(`构建失败: ${next.last_error.split('\n')[0]}`)
        else toast.success('索引已重建')
      }
    }, BUILD_POLL_MS)
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  }, [buildStatus.running, refetch, refetchBuild])

  const upload = useCallback(async (files: File[], category: RagCategory): Promise<boolean[]> => {
    setLoading(true)
    try {
      const results = await Promise.all(files.map(async (file) => {
        const form = new FormData()
        form.append('category', category)
        form.append('file', file)
        const res = await apiFetch<{ overwritten: boolean; rel_path: string }>(
          `${BASE(libId)}/files`,
          { method: 'POST', body: form, fallbackError: `上传失败: ${file.name}` },
        )
        if (res.ok) toast.success(res.data.overwritten ? `已覆盖 ${res.data.rel_path}` : `已上传 ${res.data.rel_path}`)
        return res.ok
      }))
      await refetch()
      return results
    } finally {
      setLoading(false)
    }
  }, [libId, refetch])

  const remove = useCallback(async (category: RagCategory, filename: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(
        `${BASE(libId)}/files/${category}/${encodeURIComponent(filename)}`,
        { method: 'DELETE', fallbackError: '删除失败' },
      )
      if (res.ok) { toast.success(`已删除 ${category}/${filename}`); await refetch() }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [libId, refetch])

  const rebuild = useCallback(async (): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`${BASE(libId)}/rebuild`, { method: 'POST', silent: true })
      if (!res.ok) {
        if (res.status === 409) toast.info('构建已在进行中')
        else toast.error('启动构建失败')
        return false
      }
      setBuildStatus(prev => ({ ...prev, running: true, last_error: null }))
      return true
    } finally {
      setLoading(false)
    }
  }, [libId])

  const importTranscript = useCallback(async (videoId: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<{ imported: string[]; video_id: string }>(
        `${BASE(libId)}/import-transcript`,
        { method: 'POST', body: { video_id: videoId }, fallbackError: '导入失败' },
      )
      if (res.ok) {
        toast.success(`已导入 ${res.data.imported.length} 个文件`)
        await refetch()
      }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [libId, refetch])

  return { status, buildStatus, loading, upload, remove, rebuild, importTranscript, refetch }
}
```

- [ ] **Step 7: Run frontend tests**

```bash
cd /Users/xiu/code/vision && pnpm --filter web test --run 2>&1 | grep -E "PASS|FAIL|use-rag-librar"
```
Expected: use-rag-libraries and use-rag-library both PASS

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/config/app-paths.ts apps/web/src/features/live/hooks/use-rag-libraries.ts apps/web/src/features/live/hooks/use-rag-libraries.test.ts apps/web/src/features/live/hooks/use-rag-library.ts apps/web/src/features/live/hooks/use-rag-library.test.ts
git commit -m "feat(web): add use-rag-libraries and use-rag-library hooks"
```

---

## Task 8: Frontend — Libraries pages and sidebar

**Files:**
- Create: `apps/web/src/features/live/components/rag-library/library-list.tsx`
- Create: `apps/web/src/features/live/components/rag-library/library-detail.tsx`
- Create: `apps/web/src/features/live/components/rag-library/import-transcript-tab.tsx`
- Create: `apps/web/src/app/(dashboard)/libraries/page.tsx`
- Create: `apps/web/src/app/(dashboard)/libraries/[id]/page.tsx`
- Modify: `apps/web/src/components/app-sidebar.tsx`

- [ ] **Step 1: Create library-list.tsx**

```tsx
// apps/web/src/features/live/components/rag-library/library-list.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@workspace/ui/components/button'
import { appPaths } from '@/config/app-paths'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export function LibraryList() {
  const router = useRouter()
  const { libraries, loading, createLibrary, deleteLibrary } = useRagLibraries()
  const [showCreate, setShowCreate] = useState(false)
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')

  async function handleCreate() {
    const ok = await createLibrary(newId, newName)
    if (ok) { setShowCreate(false); setNewId(''); setNewName('') }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">素材库</h1>
        <Button size="sm" onClick={() => setShowCreate(true)} disabled={loading}>
          + 新建素材库
        </Button>
      </div>

      {showCreate && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <input
            className="rounded border px-3 py-1.5 text-sm"
            placeholder="ID（小写字母+连字符，如 dong-yuhui）"
            value={newId}
            onChange={(e) => setNewId(e.target.value)}
          />
          <input
            className="rounded border px-3 py-1.5 text-sm"
            placeholder="显示名称（如 董宇辉）"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreate} disabled={loading || !newId || !newName}>
              创建
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>
              取消
            </Button>
          </div>
        </div>
      )}

      {libraries.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无素材库，点击「新建素材库」开始</p>
      ) : (
        <div className="flex flex-col gap-2">
          {libraries.map((lib) => (
            <div
              key={lib.id}
              className="flex items-center justify-between rounded-lg border p-4 cursor-pointer hover:bg-muted/50"
              onClick={() => router.push(appPaths.dashboard.library(lib.id).href)}
            >
              <div>
                <p className="text-sm font-medium">{lib.name}</p>
                <p className="text-xs text-muted-foreground">{lib.id}</p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="text-destructive hover:text-destructive"
                disabled={loading}
                onClick={(e) => { e.stopPropagation(); deleteLibrary(lib.id) }}
              >
                删除
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create import-transcript-tab.tsx**

```tsx
// apps/web/src/features/live/components/rag-library/import-transcript-tab.tsx
'use client'

import { useEffect, useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { apiFetch } from '@/lib/api-fetch'

type VideoSummary = {
  video_id: string
  title: string | null
  source: string
  duration_sec: number | null
}

type ImportedSet = Set<string>

export function ImportTranscriptTab({
  libId,
  onImport,
}: {
  libId: string
  onImport: (videoId: string) => Promise<boolean>
}) {
  const [videos, setVideos] = useState<VideoSummary[]>([])
  const [imported, setImported] = useState<ImportedSet>(new Set())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiFetch<VideoSummary[]>('api/intelligence/video-asr/videos?status=done', { silent: true }).then(
      (res) => { if (res.ok) setVideos(res.data) },
    )
  }, [])

  async function handleImport(videoId: string) {
    setLoading(true)
    try {
      const ok = await onImport(videoId)
      if (ok) setImported((prev) => new Set([...prev, videoId]))
    } finally {
      setLoading(false)
    }
  }

  if (videos.length === 0) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        暂无已完成的转录视频。先运行视频转录流程。
      </div>
    )
  }

  return (
    <div className="flex flex-col divide-y">
      {videos.map((v) => {
        const isImported = imported.has(v.video_id)
        const durationMin = v.duration_sec ? Math.round(v.duration_sec / 60) : null
        return (
          <div key={v.video_id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-sm">{v.title ?? v.video_id}</span>
              <span className="text-xs text-muted-foreground">
                {v.source}{durationMin ? ` · ${durationMin}分钟` : ''}
              </span>
            </div>
            <Button
              size="sm"
              variant={isImported ? 'outline' : 'default'}
              disabled={loading}
              onClick={() => handleImport(v.video_id)}
            >
              {isImported ? '已导入' : '导入'}
            </Button>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: Create library-detail.tsx**

```tsx
// apps/web/src/features/live/components/rag-library/library-detail.tsx
'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { useRagLibrary } from '@/features/live/hooks/use-rag-library'
import { FileList } from '@/features/live/components/rag-panel/file-list'
import { RagStatusCard } from '@/features/live/components/rag-panel/rag-status-card'
import { UploadDropzone } from '@/features/live/components/rag-panel/upload-dropzone'
import { ImportTranscriptTab } from './import-transcript-tab'

type Tab = 'files' | 'import'

export function LibraryDetail({ libId, libName }: { libId: string; libName: string }) {
  const { status, buildStatus, loading, upload, remove, rebuild, importTranscript } =
    useRagLibrary(libId)
  const [tab, setTab] = useState<Tab>('files')

  if (!status) {
    return <div className="p-6 text-sm text-muted-foreground">加载中…</div>
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{libName}</h2>
        <Button
          size="sm"
          variant={status.dirty ? 'default' : 'outline'}
          onClick={rebuild}
          disabled={loading || buildStatus.running}
        >
          {buildStatus.running ? '构建中…' : status.dirty ? '重建索引 (有未索引变更)' : '重建索引'}
        </Button>
      </div>

      <RagStatusCard status={status} />

      <div className="flex gap-2 border-b">
        <button
          type="button"
          className={`pb-2 text-sm ${tab === 'files' ? 'border-b-2 border-foreground font-medium' : 'text-muted-foreground'}`}
          onClick={() => setTab('files')}
        >
          文件
        </button>
        <button
          type="button"
          className={`pb-2 text-sm ${tab === 'import' ? 'border-b-2 border-foreground font-medium' : 'text-muted-foreground'}`}
          onClick={() => setTab('import')}
        >
          从转录导入
        </button>
      </div>

      {tab === 'files' && (
        <>
          <UploadDropzone onUpload={upload} disabled={loading || buildStatus.running} />
          <FileList sources={status.sources} onDelete={remove} disabled={loading || buildStatus.running} />
        </>
      )}

      {tab === 'import' && (
        <ImportTranscriptTab libId={libId} onImport={importTranscript} />
      )}

      {buildStatus.last_error && !buildStatus.running && (
        <div className="rounded border border-destructive bg-destructive/10 p-3 text-xs text-destructive whitespace-pre-wrap">
          上次构建失败: {buildStatus.last_error.split('\n')[0]}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create /libraries page**

```tsx
// apps/web/src/app/(dashboard)/libraries/page.tsx
import { LibraryList } from '@/features/live/components/rag-library/library-list'

export default function LibrariesPage() {
  return <LibraryList />
}
```

- [ ] **Step 5: Create /libraries/[id] page**

```tsx
// apps/web/src/app/(dashboard)/libraries/[id]/page.tsx
'use client'

import { use } from 'react'
import { useRouter } from 'next/navigation'
import { appPaths } from '@/config/app-paths'
import { LibraryDetail } from '@/features/live/components/rag-library/library-detail'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export default function LibraryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { libraries } = useRagLibraries()
  const lib = libraries.find((l) => l.id === id)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b px-6 py-3">
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => router.push(appPaths.dashboard.libraries.href)}
        >
          &larr; 素材库
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <LibraryDetail libId={id} libName={lib?.name ?? id} />
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Add sidebar entry**

In `apps/web/src/components/app-sidebar.tsx`, add to `navItems`:

```tsx
import { BookOpenIcon, DatabaseIcon, RadioIcon, Settings2Icon } from 'lucide-react'
```

```tsx
const navItems = [
  {
    title: 'Live',
    url: appPaths.dashboard.live.href,
    icon: <RadioIcon />,
    items: [],
  },
  {
    title: '方案库',
    url: appPaths.dashboard.plans.href,
    icon: <BookOpenIcon />,
    items: [],
  },
  {
    title: '素材库',
    url: appPaths.dashboard.libraries.href,
    icon: <DatabaseIcon />,
    items: [],
  },
  {
    title: 'Settings',
    url: '#',
    icon: <Settings2Icon />,
    items: [],
  },
]
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/features/live/components/rag-library/ apps/web/src/app/\(dashboard\)/libraries/ apps/web/src/components/app-sidebar.tsx
git commit -m "feat(web): add libraries pages and sidebar entry"
```

---

## Task 9: Update Plan RAG tab to library selector

**Files:**
- Create: `apps/web/src/features/live/components/plan-rag-libraries.tsx`
- Modify: `apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx`

- [ ] **Step 1: Create plan-rag-libraries.tsx**

```tsx
// apps/web/src/features/live/components/plan-rag-libraries.tsx
'use client'

import { useCallback, useEffect, useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { toast } from '@workspace/ui/components/sonner'
import { apiFetch } from '@/lib/api-fetch'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export function PlanRagLibraries({ planId }: { planId: string }) {
  const { libraries } = useRagLibraries()
  const [selected, setSelected] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiFetch<{ rag_library_ids: string[] }>(`live/plans/${planId}`, { silent: true }).then((res) => {
      if (res.ok) setSelected(res.data.rag_library_ids ?? [])
    })
  }, [planId])

  const toggle = (id: string) => {
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  const save = useCallback(async () => {
    setSaving(true)
    try {
      const res = await apiFetch(`live/plans/${planId}/rag-libraries`, {
        method: 'PUT',
        body: { library_ids: selected },
        fallbackError: '保存失败',
      })
      if (res.ok) toast.success('已保存关联素材库')
    } finally {
      setSaving(false)
    }
  }, [planId, selected])

  if (libraries.length === 0) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        暂无素材库。请先在「素材库」页面创建。
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h2 className="text-base font-semibold">关联素材库</h2>
      <p className="text-sm text-muted-foreground">勾选后点击保存，直播时 AI 导播将从这些库中检索话术参考。</p>
      <div className="flex flex-col gap-2">
        {libraries.map((lib) => (
          <label key={lib.id} className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/50">
            <input
              type="checkbox"
              checked={selected.includes(lib.id)}
              onChange={() => toggle(lib.id)}
            />
            <div>
              <p className="text-sm font-medium">{lib.name}</p>
              <p className="text-xs text-muted-foreground">{lib.id}</p>
            </div>
          </label>
        ))}
      </div>
      <Button size="sm" onClick={save} disabled={saving}>
        {saving ? '保存中…' : '保存'}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Update /plans/[id]/rag/page.tsx**

```tsx
// apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx
'use client'

import { use } from 'react'
import { useRouter } from 'next/navigation'

import { appPaths } from '@/config/app-paths'
import { PlanRagLibraries } from '@/features/live/components/plan-rag-libraries'

export default function PlanRagPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b px-6 py-3">
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => router.push(appPaths.dashboard.plan(id).href)}
        >
          &larr; 方案编辑
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <PlanRagLibraries planId={id} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/live/components/plan-rag-libraries.tsx apps/web/src/app/\(dashboard\)/plans/\[id\]/rag/page.tsx
git commit -m "feat(web): replace plan RAG tab with library selector"
```

---

## Task 10: Add video list endpoint for import tab

**Files:**
- Modify: `python-packages/api/src/vision_api/video_asr_routes.py`

The `ImportTranscriptTab` component fetches `api/intelligence/video-asr/videos?status=done`. This endpoint needs to exist.

- [ ] **Step 1: Write failing test**

Add to `python-packages/api/src/vision_api/video_asr_routes_test.py`:

```python
async def test_list_videos_empty(client):
    r = await client.get("/api/intelligence/video-asr/videos")
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest python-packages/api/src/vision_api/video_asr_routes_test.py::test_list_videos_empty -v
```
Expected: 404

- [ ] **Step 3: Add endpoint to video_asr_routes.py**

In `python-packages/api/src/vision_api/video_asr_routes.py`, add:

```python
@router.get("/videos")
async def list_videos(request: Request) -> list[dict]:
    """List all processed videos (those with a completed pipeline)."""
    from vision_intelligence.video_asr.storage import VideoAsrStorage
    st: VideoAsrStorage = request.app.state.video_asr_storage
    rows = await st.list_videos()
    return rows
```

Then add `list_videos` to `VideoAsrStorage` in `python-packages/intelligence/src/vision_intelligence/video_asr/storage.py`:

```python
async def list_videos(self) -> list[dict]:
    """Return id, title, source, duration_sec for all video_sources rows."""
    rows = []
    async with self._conn.execute(
        "SELECT video_id, title, source, duration_sec FROM video_sources ORDER BY downloaded_at DESC"
    ) as cur:
        async for row in cur:
            rows.append({
                "video_id": row[0],
                "title": row[1],
                "source": row[2],
                "duration_sec": row[3],
            })
    return rows
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest python-packages/api/src/vision_api/video_asr_routes_test.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add python-packages/api/src/vision_api/video_asr_routes.py python-packages/intelligence/src/vision_intelligence/video_asr/storage.py python-packages/api/src/vision_api/video_asr_routes_test.py
git commit -m "feat(api): add GET /video-asr/videos endpoint for library import"
```

---

## Task 11: Full test run and cleanup

- [ ] **Step 1: Run all Python tests**

```bash
cd /Users/xiu/code/vision
uv run pytest python-packages/ -v --tb=short 2>&1 | tail -30
```
Expected: all PASSED, 0 failures

- [ ] **Step 2: Run all frontend tests**

```bash
pnpm --filter web test --run 2>&1 | tail -20
```
Expected: all PASSED

- [ ] **Step 3: Type-check frontend**

```bash
pnpm --filter web exec tsc --noEmit 2>&1 | head -30
```
Expected: no errors

- [ ] **Step 4: Final commit if any loose files**

```bash
git status
```
If clean, done. If any stragglers:
```bash
git add -p
git commit -m "chore: cleanup after rag-library implementation"
```
