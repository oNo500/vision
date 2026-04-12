"""KnowledgeBase — loads product YAML and exposes a context string for LLM prompts."""
from __future__ import annotations

from pathlib import Path

import yaml


class KnowledgeBase:
    """Loads product knowledge from a YAML file.

    Args:
        path: Path to product YAML file.
    """

    def __init__(self, path: str | Path) -> None:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected a YAML mapping, got {type(data).__name__}")
        self._product = data.get("product", {})
        self._rules = data.get("rules", {})

    @property
    def product_name(self) -> str:
        return self._product.get("name", "")

    @property
    def banned_words(self) -> list[str]:
        return self._rules.get("banned_words", [])

    def must_mention_for_segment(self, segment_id: str) -> list[str]:
        return self._rules.get("must_mention_per_segment", {}).get(segment_id, [])

    def context_for_prompt(self) -> str:
        """Return a compact product knowledge block for inclusion in LLM prompts."""
        p = self._product
        lines = [
            f"【产品】{p.get('name', '')} — {p.get('tagline', '')}",
            f"【价格】直播价 ¥{p.get('price', '')}（原价 ¥{p.get('original_price', '')}）",
            "【卖点】",
        ]
        for sp in p.get("selling_points", []):
            lines.append(f"  - {sp}")
        lines.append("【常见问题】")
        for faq in p.get("faqs", []):
            lines.append(f"  Q: {faq.get('q', '')}")
            lines.append(f"  A: {faq.get('a', '')}")
        return "\n".join(lines)
