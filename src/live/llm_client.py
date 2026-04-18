"""LLMClient — thin LiteLLM wrapper for provider-agnostic chat completion.

Used by DirectorAgent via a `generate(prompt)` callable. Switching between
Vertex AI, Vercel AI Gateway, Anthropic, OpenAI, etc. is a configuration
change; the caller signature stays stable.
"""
from __future__ import annotations

import logging

from litellm import completion

logger = logging.getLogger(__name__)


class LLMClient:
    """Provider-agnostic single-turn LLM caller.

    Args:
        model: LiteLLM-qualified model name, e.g. "vertex_ai/gemini-2.5-flash",
            "vercel/gemini-2.5-flash", "anthropic/claude-sonnet-4-6".
        api_base: Override endpoint (Vercel AI Gateway, self-hosted, ...).
        api_key: API key for non-Vertex providers.
        project: GCP project ID — only used when routing via Vertex AI (ADC auth).
    """

    def __init__(
        self,
        model: str,
        api_base: str | None = None,
        api_key: str | None = None,
        project: str | None = None,
    ) -> None:
        self._model = model
        self._api_base = api_base
        self._api_key = api_key
        self._vertex_project = project
        logger.info("LLMClient initialized (model=%s)", model)

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Single-turn completion. Returns the raw response content."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._vertex_project:
            kwargs["vertex_project"] = self._vertex_project
            kwargs["vertex_location"] = "us-central1"

        response = completion(**kwargs)
        return response.choices[0].message.content or ""
