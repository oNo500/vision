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
