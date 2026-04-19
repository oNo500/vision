"""RAG retrieval for DirectorAgent — TalkPointRAG queries ChromaDB collections."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from vision_live.embedder import Embedder, get_default_embedder

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
