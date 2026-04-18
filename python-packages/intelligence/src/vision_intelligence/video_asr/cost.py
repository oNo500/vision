"""LLM cost estimator (USD)."""
from __future__ import annotations

# prices in USD per 1M tokens
_PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
}


def estimate_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float:
    p = _PRICING.get(model)
    if p is None:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
