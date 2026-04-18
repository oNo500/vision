"""End-to-end RAG test with real bge-base + ChromaDB.

Marked slow because it downloads ~400MB on first run. Run explicitly with:

    uv run pytest python-packages/live/src/vision_live/rag_integration_test.py -m slow -v

Skipped by default so CI / normal runs stay fast.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vision_live.rag_cli import cmd_build

pytestmark = pytest.mark.slow


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def plan_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up isolated data/ and .rag/ roots under tmp_path."""
    data_root = tmp_path / "data" / "talk_points"
    index_root = tmp_path / ".rag"

    monkeypatch.setattr("vision_live.rag_cli.DATA_ROOT", data_root)
    monkeypatch.setattr("vision_live.rag_cli.INDEX_ROOT", index_root)

    plan_id = "integration-plan"
    plan_root = data_root / plan_id

    _write(plan_root / "scripts" / "opening.md", "大家好欢迎来到直播间,今天带来新款益生菌。")
    _write(
        plan_root / "product_manual" / "spec.md",
        "本款益生菌每条含 2000 亿活性菌,采用纯植物萃取工艺。"
        "\n\n适合 6 个月以上宝宝饮用,每日一条,饭后温水冲服。",
    )
    _write(
        plan_root / "competitor_clips" / "viral.md",
        "姐妹们这个活菌数真的炸裂,我家宝宝喝了一周排便都规律了。",
    )
    _write(plan_root / "qa_log" / "faq.md", "Q: 敏感体质能喝吗\nA: 纯植物配方,无添加,放心喝。")

    return plan_id, data_root, index_root


def test_build_creates_index_and_loads(plan_dirs):
    plan_id, data_root, index_root = plan_dirs

    rc = cmd_build(plan_id)
    assert rc == 0

    assert (index_root / plan_id / "meta.json").exists()
    # chroma.sqlite3 is created by ChromaDB PersistentClient
    assert any(
        p.name.startswith("chroma")
        for p in (index_root / plan_id).iterdir()
    )


def test_query_retrieves_semantic_matches(plan_dirs, monkeypatch: pytest.MonkeyPatch):
    from vision_live.rag import load_rag_for_plan

    plan_id, _, index_root = plan_dirs
    cmd_build(plan_id)

    rag = load_rag_for_plan(plan_id, rag_root=index_root)
    assert rag is not None

    # Query about ingredient count → should hit at least one of the two
    # documents that mention 活菌 (spec.md or viral.md). We don't pin the
    # exact ranking — both are semantically valid hits and ranking depends
    # on model internals.
    points = rag.query("成分有多少活菌", [], k=3)
    assert points, "expected at least one hit for ingredient query"
    top_sources = {p.source for p in points}
    activemenu_sources = {"product_manual/spec.md", "competitor_clips/viral.md"}
    assert top_sources & activemenu_sources, (
        f"expected a hit from {activemenu_sources}, got {top_sources}"
    )


def test_incremental_build_skips_unchanged(plan_dirs, capsys):
    plan_id, _, _ = plan_dirs

    rc1 = cmd_build(plan_id)
    assert rc1 == 0

    # second run with no changes → "up to date"
    rc2 = cmd_build(plan_id)
    assert rc2 == 0
    captured = capsys.readouterr()
    assert "up to date" in captured.out


def test_query_unrelated_topic_may_return_nothing(plan_dirs):
    from vision_live.rag import load_rag_for_plan

    plan_id, _, index_root = plan_dirs
    cmd_build(plan_id)

    rag = load_rag_for_plan(plan_id, rag_root=index_root)
    # deliberately unrelated query; threshold 0.5 may filter everything
    points = rag.query("股票基金房地产投资", [], k=3)
    # either empty or very few — we just assert the call doesn't error
    assert isinstance(points, list)
