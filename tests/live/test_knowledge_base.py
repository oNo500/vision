"""Tests for KnowledgeBase."""
import textwrap
from pathlib import Path

import pytest

from scripts.live.knowledge_base import KnowledgeBase


SAMPLE_YAML = textwrap.dedent("""\
    product:
      name: "超能面膜"
      tagline: "28天焕新肌肤"
      price: 99
      original_price: 199
      selling_points:
        - "纯植物萃取，无添加"
        - "买二送一，今天限定"
        - "明星同款，已卖出10万套"
      faqs:
        - q: "适合什么肤质？"
          a: "所有肤质均可用，敏感肌也没问题"
        - q: "怎么购买？"
          a: "点左下角购物车直接下单"
    rules:
      banned_words:
        - "最好"
        - "第一"
      must_mention_per_segment:
        product_core: ["纯植物", "买二送一"]
""")


@pytest.fixture
def kb(tmp_path):
    p = tmp_path / "product.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    return KnowledgeBase(str(p))


def test_product_name(kb):
    assert kb.product_name == "超能面膜"


def test_context_contains_selling_points(kb):
    ctx = kb.context_for_prompt()
    assert "纯植物萃取" in ctx
    assert "买二送一" in ctx


def test_context_contains_faqs(kb):
    ctx = kb.context_for_prompt()
    assert "适合什么肤质" in ctx
    assert "所有肤质均可用" in ctx


def test_banned_words(kb):
    assert "最好" in kb.banned_words
    assert "第一" in kb.banned_words


def test_must_mention(kb):
    words = kb.must_mention_for_segment("product_core")
    assert "纯植物" in words
    assert kb.must_mention_for_segment("opening") == []
