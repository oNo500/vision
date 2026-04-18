"""Paragraph-level markdown chunker for RAG indexing.

Splits a document into ~500-char chunks on semantic boundaries:
- blank line separates paragraphs
- headings (#, ##, ###) are hard separators (chunks never span them)
- fenced code blocks (```...```) stay intact as a single chunk
- list items (- / 1.) stay grouped together

No overlap between chunks.
"""
from __future__ import annotations

import re

_TARGET_SIZE = 500
_MAX_SIZE = 600
_SENTENCE_ENDERS = ("。", "？", "！")

_HEADING_RE = re.compile(r"^#{1,6}\s")
_LIST_ITEM_RE = re.compile(r"^(?:[-*+]\s|\d+\.\s)")
_CODE_FENCE = "```"


def chunk_markdown(text: str) -> list[str]:
    """Split markdown text into chunks.

    Returns a list of chunk strings (each trimmed, no trailing whitespace).
    Empty / whitespace-only input yields an empty list.
    """
    if not text or not text.strip():
        return []

    blocks = _split_into_blocks(text)
    chunks: list[str] = []

    pending: list[str] = []

    def flush() -> None:
        if pending:
            chunks.append("\n\n".join(pending).strip())
            pending.clear()

    for block in blocks:
        is_heading = _HEADING_RE.match(block) is not None
        is_code = block.startswith(_CODE_FENCE)

        # Heading is a hard separator — flush pending, start a new chunk with the heading.
        if is_heading:
            flush()
            pending.append(block)
            continue

        # Code blocks stay intact, whatever their size.
        if is_code:
            flush()
            chunks.append(block.strip())
            continue

        # Oversized plain block → split by sentence.
        if len(block) > _MAX_SIZE:
            flush()
            for sub in _split_by_sentence(block):
                chunks.append(sub.strip())
            continue

        tentative = "\n\n".join([*pending, block])
        if len(tentative) > _MAX_SIZE:
            flush()
            pending.append(block)
        else:
            pending.append(block)

    flush()
    return [c for c in chunks if c]


def _split_into_blocks(text: str) -> list[str]:
    """Split text into blocks.

    Blocks are separated by blank lines; fenced code blocks and contiguous
    list-item lines are preserved as single blocks.
    """
    lines = text.splitlines()
    blocks: list[str] = []
    buf: list[str] = []
    i = 0

    def flush_buf() -> None:
        if buf:
            blocks.append("\n".join(buf).rstrip())
            buf.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # fenced code block: accumulate until closing fence
        if stripped.startswith(_CODE_FENCE):
            flush_buf()
            code_lines = [line]
            i += 1
            while i < len(lines):
                code_lines.append(lines[i])
                if lines[i].strip().startswith(_CODE_FENCE):
                    i += 1
                    break
                i += 1
            blocks.append("\n".join(code_lines))
            continue

        # blank line → block separator
        if not stripped:
            flush_buf()
            i += 1
            continue

        buf.append(line)
        i += 1

    flush_buf()
    return [b for b in blocks if b.strip()]


def _split_by_sentence(text: str) -> list[str]:
    """Split an oversized single block by sentence enders, packing to target size."""
    # Keep sentence enders attached to their sentence.
    pattern = f"([{''.join(_SENTENCE_ENDERS)}])"
    parts = re.split(pattern, text)
    # parts like ["句1", "。", "句2", "？", ""] → re-pair into ["句1。", "句2?"]
    sentences: list[str] = []
    for j in range(0, len(parts), 2):
        body = parts[j]
        ender = parts[j + 1] if j + 1 < len(parts) else ""
        s = (body + ender).strip()
        if s:
            sentences.append(s)

    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if not buf:
            buf = s
            continue
        if len(buf) + len(s) > _MAX_SIZE:
            chunks.append(buf)
            buf = s
        else:
            buf += s
    if buf:
        chunks.append(buf)
    return chunks
