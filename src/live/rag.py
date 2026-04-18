"""RAG retrieval for DirectorAgent — TalkPointRAG queries a ChromaDB collection.

The embedder and collection are injected so tests can substitute lightweight
fakes without pulling in torch or HuggingFace. Production wiring lives in
``load_rag_for_plan`` (used by SessionManager).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

_DEFAULT_MIN_SCORE = 0.5
_DEFAULT_K = 5


@dataclass
class TalkPoint:
    """A single retrieved chunk plus enough metadata to attribute it in the prompt."""

    id: str
    text: str
    source: str
    category: str
    chunk_index: int


class _Embedder(Protocol):
    def encode(self, text: str): ...


def _build_query(segment_goal: str, recent_danmaku: list[str]) -> str:
    """Concatenate the segment goal with up to the last 3 danmaku texts."""
    danmaku_tail = " ".join(recent_danmaku[-3:])
    return f"{segment_goal} {danmaku_tail}".strip()


class TalkPointRAG:
    """Semantic retrieval over a per-plan ChromaDB collection.

    Args:
        collection: any object with a ``query(**kwargs)`` method matching
            ChromaDB's ``Collection.query`` shape.
        embedder: any object with ``encode(text)`` returning a list/array of floats.
        min_score: cosine similarity floor; chunks below are dropped silently.
    """

    def __init__(
        self,
        collection,
        embedder: _Embedder,
        min_score: float = _DEFAULT_MIN_SCORE,
    ) -> None:
        self._collection = collection
        self._embedder = embedder
        self._min_score = min_score

    def query(
        self,
        segment_goal: str,
        recent_danmaku: list[str],
        k: int = _DEFAULT_K,
    ) -> list[TalkPoint]:
        query_text = _build_query(segment_goal, recent_danmaku)
        embedding = self._embedder.encode(query_text)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()

        results = self._collection.query(
            query_embeddings=[list(embedding)],
            n_results=k,
        )

        docs = _first(results.get("documents"))
        metas = _first(results.get("metadatas"))
        distances = _first(results.get("distances"))

        points: list[TalkPoint] = []
        for doc, meta, dist in zip(docs, metas, distances, strict=True):
            similarity = 1.0 - float(dist)
            if similarity < self._min_score:
                continue
            points.append(TalkPoint(
                id=str(meta.get("id", "")),
                text=doc,
                source=str(meta.get("source", "")),
                category=str(meta.get("category", "")),
                chunk_index=int(meta.get("chunk_index", 0)),
            ))
        return points


def _first(maybe_nested) -> list:
    """Chroma wraps per-query results in an outer list; unwrap the first query's list."""
    if not maybe_nested:
        return []
    if isinstance(maybe_nested, list) and maybe_nested and isinstance(maybe_nested[0], list):
        return maybe_nested[0]
    return list(maybe_nested)


def load_rag_for_plan(plan_id: str, rag_root: str | Path = ".rag") -> TalkPointRAG | None:
    """Open a pre-built index for the given plan; return None if missing.

    Lazy-imports chromadb and sentence-transformers so the dependency is only
    required on the production path, not in unit tests.
    """
    path = Path(rag_root) / plan_id
    if not (path / "chroma.sqlite3").exists() and not (path / "chroma.sqlite").exists():
        logger.info("RAG: no index at %s, skipping", path)
        return None

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        logger.warning("RAG unavailable, missing deps: %s", e)
        return None

    client = chromadb.PersistentClient(path=str(path))
    collection_name = f"talkpoints_{plan_id}"
    try:
        collection = client.get_collection(collection_name)
    except Exception as e:
        logger.warning("RAG: collection %s not found: %s", collection_name, e)
        return None

    embedder = SentenceTransformer("BAAI/bge-base-zh-v1.5")
    return TalkPointRAG(collection, embedder)
