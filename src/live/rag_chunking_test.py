"""Tests for chunk_markdown — paragraph-level splitter for RAG indexing."""
from __future__ import annotations

from src.live.rag_chunking import chunk_markdown


def _len(chunks: list[str]) -> list[int]:
    return [len(c) for c in chunks]


# ---------------------------------------------------------------------------
# basic length handling
# ---------------------------------------------------------------------------


def test_short_document_becomes_single_chunk():
    text = "这是一段简短的开场白。"
    chunks = chunk_markdown(text)
    assert chunks == [text]


def test_empty_document_returns_empty_list():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n\n  \n") == []


def test_paragraphs_packed_until_target_size():
    paragraphs = ["一段文字,约一百字。" * 10] * 3   # each ~100 chars
    text = "\n\n".join(paragraphs)
    chunks = chunk_markdown(text)
    # packing 3 × 100 chars = 300 → one chunk (under 600)
    assert len(chunks) == 1


def test_packing_splits_when_exceeding_max():
    # 5 paragraphs of 200 chars each → 1000 total → split into 2 chunks
    paragraphs = ["段落内容" * 50 for _ in range(5)]   # 200 chars each
    text = "\n\n".join(paragraphs)
    chunks = chunk_markdown(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 600 for c in chunks)


def test_single_paragraph_exceeding_max_is_split_by_sentence():
    # Single 1500-char paragraph with sentence boundaries
    sentence = "这是一个完整的句子。"   # 10 chars
    text = sentence * 150    # 1500 chars, no paragraph breaks
    chunks = chunk_markdown(text)
    assert len(chunks) >= 3
    # Each chunk should end on a sentence boundary
    for c in chunks:
        assert c.endswith("。") or c.endswith("？") or c.endswith("！")


# ---------------------------------------------------------------------------
# markdown headings as hard separators
# ---------------------------------------------------------------------------


def test_heading_starts_new_chunk():
    text = (
        "# 开场\n"
        "大家好欢迎来到直播间。\n\n"
        "# 产品介绍\n"
        "今天带来的是新款超能面膜。"
    )
    chunks = chunk_markdown(text)
    assert len(chunks) == 2
    assert "开场" in chunks[0]
    assert "产品介绍" in chunks[1]


def test_h2_and_h3_also_separate():
    text = "## 段 A\n内容 A。\n\n### 段 B\n内容 B。"
    chunks = chunk_markdown(text)
    assert len(chunks) == 2


def test_heading_does_not_split_when_content_is_tiny():
    """Even tiny sections keep the heading with their content,
    but headings ARE still hard separators (we don't merge across them)."""
    text = "# A\n内容 A。\n\n# B\n内容 B。"
    chunks = chunk_markdown(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("# A")
    assert chunks[1].startswith("# B")


# ---------------------------------------------------------------------------
# code blocks stay intact
# ---------------------------------------------------------------------------


def test_code_block_not_split():
    code = "```python\n" + "print('x')\n" * 100 + "```"   # big code block
    text = f"前言。\n\n{code}\n\n结尾。"
    chunks = chunk_markdown(text)
    # the code block must appear whole in exactly one chunk
    code_chunks = [c for c in chunks if "```python" in c]
    assert len(code_chunks) == 1
    assert code_chunks[0].count("```") == 2


def test_code_block_inline_with_prose():
    text = "第一段说明。\n\n```\nsome code\n```\n\n第二段说明。"
    chunks = chunk_markdown(text)
    joined = "\n".join(chunks)
    assert "some code" in joined


# ---------------------------------------------------------------------------
# lists stay intact
# ---------------------------------------------------------------------------


def test_list_items_stay_in_same_chunk():
    text = (
        "卖点清单:\n\n"
        "- 成分 1:益生菌\n"
        "- 成分 2:胶原蛋白\n"
        "- 成分 3:玻尿酸\n"
    )
    chunks = chunk_markdown(text)
    # list must not be split mid-way
    list_chunks = [c for c in chunks if "- 成分 1" in c]
    assert len(list_chunks) == 1
    assert "- 成分 3" in list_chunks[0]


def test_numbered_list_stays_intact():
    text = "步骤:\n\n1. 打开包装\n2. 敷 15 分钟\n3. 揭下清洗"
    chunks = chunk_markdown(text)
    list_chunks = [c for c in chunks if "1. 打开包装" in c]
    assert len(list_chunks) == 1
    assert "3. 揭下清洗" in list_chunks[0]


# ---------------------------------------------------------------------------
# whitespace + normalisation
# ---------------------------------------------------------------------------


def test_leading_trailing_whitespace_trimmed():
    chunks = chunk_markdown("   \n\n内容。\n\n   ")
    assert chunks == ["内容。"]


def test_multiple_blank_lines_treated_as_one_break():
    text = "段 A。\n\n\n\n段 B。"
    chunks = chunk_markdown(text)
    # joined, both pieces present
    joined = "\n".join(chunks)
    assert "段 A" in joined and "段 B" in joined
