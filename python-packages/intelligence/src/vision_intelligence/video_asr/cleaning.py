"""Text cleaning per spec §6.5."""
from __future__ import annotations

import re

import jieba
from opencc import OpenCC

_OCC = OpenCC("t2s")

# Map halfwidth punctuation that follows CJK to fullwidth.
_CJK = r"[\u4e00-\u9fff]"
_HALF_TO_FULL = {",": "，", ".": "。", "?": "？", "!": "！", ";": "；", ":": "："}


def normalize_punctuation(s: str) -> str:
    def _repl(m):
        return m.group(1) + _HALF_TO_FULL[m.group(2)]
    pattern = re.compile(rf"({_CJK})([,.?!;:])")
    return pattern.sub(_repl, s)


def traditional_to_simplified(s: str) -> str:
    return _OCC.convert(s)


def jieba_tokenize(s: str) -> str:
    """Return space-separated tokens for FTS5 indexing."""
    return " ".join(w for w in jieba.cut(s) if w.strip())
