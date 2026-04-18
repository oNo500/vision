"""Tests for KnowledgeBase YAML loader."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.live.knowledge_base import KnowledgeBase


@pytest.fixture
def product_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "product.yaml"
    path.write_text(
        textwrap.dedent(
            """\
            product:
              name: 超能面膜
              tagline: 28 天焕新
              price: 99
              original_price: 199
              selling_points:
                - 纯植物萃取
                - 28天看得见
              faqs:
                - q: 适合油皮吗
                  a: 适合所有肤质
                - q: 敏感肌能用吗
                  a: 先做耳后测试
            rules:
              banned_words:
                - 假货
                - 三无
              must_mention_per_segment:
                product_core:
                  - 纯植物
                  - 无添加
            """
        ),
        encoding="utf-8",
    )
    return path


def test_product_name(product_yaml: Path):
    kb = KnowledgeBase(product_yaml)
    assert kb.product_name == "超能面膜"


def test_banned_words(product_yaml: Path):
    kb = KnowledgeBase(product_yaml)
    assert kb.banned_words == ["假货", "三无"]


def test_must_mention_for_known_segment(product_yaml: Path):
    kb = KnowledgeBase(product_yaml)
    assert kb.must_mention_for_segment("product_core") == ["纯植物", "无添加"]


def test_must_mention_for_unknown_segment_returns_empty(product_yaml: Path):
    kb = KnowledgeBase(product_yaml)
    assert kb.must_mention_for_segment("unknown") == []


def test_context_contains_selling_points(product_yaml: Path):
    ctx = KnowledgeBase(product_yaml).context_for_prompt()
    assert "纯植物萃取" in ctx
    assert "28天看得见" in ctx


def test_context_contains_faqs(product_yaml: Path):
    ctx = KnowledgeBase(product_yaml).context_for_prompt()
    assert "适合油皮吗" in ctx
    assert "先做耳后测试" in ctx


def test_context_contains_price(product_yaml: Path):
    ctx = KnowledgeBase(product_yaml).context_for_prompt()
    assert "99" in ctx and "199" in ctx


def test_missing_keys_return_defaults(tmp_path: Path):
    path = tmp_path / "empty.yaml"
    path.write_text("product: {}\nrules: {}\n", encoding="utf-8")
    kb = KnowledgeBase(path)
    assert kb.product_name == ""
    assert kb.banned_words == []
    assert kb.must_mention_for_segment("any") == []


def test_non_mapping_yaml_raises(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("- just a list\n- of items\n", encoding="utf-8")
    with pytest.raises(ValueError):
        KnowledgeBase(path)
