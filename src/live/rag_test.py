"""Tests for TalkPointRAG — retrieval layer over a ChromaDB collection."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.live.rag import TalkPoint, TalkPointRAG, _build_query


# ---------------------------------------------------------------------------
# _build_query
# ---------------------------------------------------------------------------


def test_build_query_concatenates_goal_and_recent_danmaku():
    q = _build_query("介绍产品亮点", ["怎么吃", "多少钱", "什么时候发货"])
    assert "介绍产品亮点" in q
    assert "怎么吃" in q
    assert "多少钱" in q


def test_build_query_only_last_3_danmaku():
    q = _build_query("goal", ["d1", "d2", "d3", "d4", "d5"])
    assert "d1" not in q
    assert "d2" not in q
    assert "d5" in q


def test_build_query_handles_empty_danmaku():
    assert _build_query("goal", []) == "goal"


def test_build_query_strips_extra_whitespace():
    assert _build_query("  goal  ", []) == "goal"


# ---------------------------------------------------------------------------
# TalkPointRAG.query — high-score hits pass through
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Mock embedder returning a fixed vector; records the last input."""

    def __init__(self) -> None:
        self.last_input: str | None = None

    def encode(self, text: str):
        self.last_input = text
        return [0.1, 0.2, 0.3]


class _FakeCollection:
    """Minimal ChromaDB collection stub."""

    def __init__(self, docs: list[str], metas: list[dict], distances: list[float]) -> None:
        self._docs = docs
        self._metas = metas
        self._distances = distances
        self.last_kwargs: dict | None = None

    def query(self, **kwargs):
        self.last_kwargs = kwargs
        return {
            "documents": [self._docs],
            "metadatas": [self._metas],
            "distances": [self._distances],
        }


def _meta(idx: int, source: str = "scripts/a.md", category: str = "scripts") -> dict:
    return {
        "id": f"id-{idx}",
        "source": source,
        "category": category,
        "chunk_index": idx,
    }


def test_query_returns_points_above_threshold():
    coll = _FakeCollection(
        docs=["话术 A", "话术 B"],
        metas=[_meta(0), _meta(1)],
        distances=[0.2, 0.3],   # sim 0.8 and 0.7
    )
    rag = TalkPointRAG(coll, _FakeEmbedder(), min_score=0.5)
    points = rag.query("goal", [], k=2)

    assert len(points) == 2
    assert points[0].text == "话术 A"
    assert points[0].source == "scripts/a.md"
    assert points[0].category == "scripts"


def test_query_filters_below_threshold():
    coll = _FakeCollection(
        docs=["high", "low"],
        metas=[_meta(0), _meta(1)],
        distances=[0.1, 0.8],   # sim 0.9 and 0.2
    )
    rag = TalkPointRAG(coll, _FakeEmbedder(), min_score=0.5)
    points = rag.query("goal", [], k=2)

    assert len(points) == 1
    assert points[0].text == "high"


def test_query_all_below_threshold_returns_empty():
    coll = _FakeCollection(
        docs=["low1", "low2"],
        metas=[_meta(0), _meta(1)],
        distances=[0.7, 0.9],   # both low sim
    )
    rag = TalkPointRAG(coll, _FakeEmbedder(), min_score=0.5)
    assert rag.query("goal", []) == []


def test_query_empty_collection_returns_empty():
    coll = _FakeCollection(docs=[], metas=[], distances=[])
    rag = TalkPointRAG(coll, _FakeEmbedder())
    assert rag.query("goal", []) == []


# ---------------------------------------------------------------------------
# TalkPointRAG.query — wiring
# ---------------------------------------------------------------------------


def test_query_passes_embedding_to_collection():
    coll = _FakeCollection(docs=[], metas=[], distances=[])
    embedder = _FakeEmbedder()
    rag = TalkPointRAG(coll, embedder)

    rag.query("segment goal", ["d1"], k=7)

    assert embedder.last_input is not None
    assert "segment goal" in embedder.last_input
    assert "d1" in embedder.last_input

    assert coll.last_kwargs is not None
    assert coll.last_kwargs["n_results"] == 7
    assert coll.last_kwargs["query_embeddings"] == [[0.1, 0.2, 0.3]]


def test_query_default_k_is_5():
    coll = _FakeCollection(docs=[], metas=[], distances=[])
    rag = TalkPointRAG(coll, _FakeEmbedder())
    rag.query("goal", [])
    assert coll.last_kwargs["n_results"] == 5


def test_embedder_exception_propagates():
    class BoomEmbedder:
        def encode(self, _text):
            raise RuntimeError("oom")

    rag = TalkPointRAG(_FakeCollection([], [], []), BoomEmbedder())
    with pytest.raises(RuntimeError):
        rag.query("goal", [])


# ---------------------------------------------------------------------------
# TalkPoint dataclass
# ---------------------------------------------------------------------------


def test_talk_point_fields():
    tp = TalkPoint(id="x", text="t", source="s.md", category="scripts", chunk_index=3)
    assert tp.id == "x" and tp.chunk_index == 3
