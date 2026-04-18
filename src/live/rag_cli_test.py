"""Tests for rag_cli file-scanning and metadata logic (no real embedder)."""
from __future__ import annotations

import json
from pathlib import Path

from src.live.rag_cli import (
    _compute_file_hash,
    _diff_sources,
    _load_meta,
    _save_meta,
    _scan_sources,
)


def test_scan_sources_picks_up_md_and_txt(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "opening.md").write_text("hello", encoding="utf-8")
    (tmp_path / "scripts" / "notes.txt").write_text("note", encoding="utf-8")
    (tmp_path / "scripts" / "ignored.png").write_bytes(b"\x89PNG")

    sources = _scan_sources(tmp_path)

    rels = sorted(s.rel_path for s in sources)
    assert rels == ["scripts/notes.txt", "scripts/opening.md"]


def test_scan_sources_only_known_categories(tmp_path: Path):
    # known category
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.md").write_text("a", encoding="utf-8")
    # unknown category — must be ignored
    (tmp_path / "random").mkdir()
    (tmp_path / "random" / "b.md").write_text("b", encoding="utf-8")

    sources = _scan_sources(tmp_path)

    rels = [s.rel_path for s in sources]
    assert "scripts/a.md" in rels
    assert "random/b.md" not in rels


def test_scan_sources_assigns_category_from_dir(tmp_path: Path):
    (tmp_path / "product_manual").mkdir()
    (tmp_path / "product_manual" / "spec.md").write_text("x", encoding="utf-8")

    sources = _scan_sources(tmp_path)

    assert sources[0].category == "product_manual"


def test_scan_sources_recursive_subdirs(tmp_path: Path):
    (tmp_path / "scripts" / "sub").mkdir(parents=True)
    (tmp_path / "scripts" / "sub" / "nested.md").write_text("x", encoding="utf-8")

    sources = _scan_sources(tmp_path)
    rels = [s.rel_path for s in sources]
    assert "scripts/sub/nested.md" in rels


def test_compute_file_hash_stable(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("hello", encoding="utf-8")
    h1 = _compute_file_hash(f)
    h2 = _compute_file_hash(f)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_file_hash_changes_on_content(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("hello", encoding="utf-8")
    h1 = _compute_file_hash(f)
    f.write_text("world", encoding="utf-8")
    h2 = _compute_file_hash(f)
    assert h1 != h2


def test_load_save_meta_roundtrip(tmp_path: Path):
    path = tmp_path / "meta.json"
    data = {"build_time": "t", "sources": {"a.md": {"sha256": "h", "chunks": 3}}}
    _save_meta(path, data)
    assert _load_meta(path) == data


def test_load_meta_missing_returns_empty(tmp_path: Path):
    assert _load_meta(tmp_path / "none.json") == {}


def test_diff_sources_detects_added_and_changed():
    prev = {
        "scripts/kept.md": {"sha256": "same"},
        "scripts/stale.md": {"sha256": "old"},
    }
    current = {
        "scripts/kept.md": "same",
        "scripts/stale.md": "new",
        "scripts/added.md": "fresh",
    }

    added_or_changed, removed = _diff_sources(prev, current)
    assert set(added_or_changed) == {"scripts/stale.md", "scripts/added.md"}
    assert set(removed) == set()


def test_diff_sources_detects_removed():
    prev = {"scripts/keep.md": {"sha256": "x"}, "scripts/gone.md": {"sha256": "y"}}
    current = {"scripts/keep.md": "x"}
    added_or_changed, removed = _diff_sources(prev, current)
    assert added_or_changed == []
    assert removed == ["scripts/gone.md"]


def test_diff_sources_all_unchanged_returns_empty():
    prev = {"a.md": {"sha256": "h"}}
    current = {"a.md": "h"}
    added_or_changed, removed = _diff_sources(prev, current)
    assert added_or_changed == [] and removed == []
