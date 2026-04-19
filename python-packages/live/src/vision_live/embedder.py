"""Embedding abstraction — production uses Vertex AI, tests use FakeEmbedder."""
from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

_MODEL = "text-multilingual-embedding-002"
_BATCH_SIZE = 250  # Vertex AI limit per request


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Zero-vector embedder for tests. Never calls any external service."""

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]


class VertexEmbedder:
    """Calls Vertex AI text-multilingual-embedding-002."""

    def __init__(
        self,
        project: str | None = None,
        location: str = "us-central1",
        model: str = _MODEL,
    ) -> None:
        self._project = project
        self._location = location
        self._model = model
        self._client = None  # lazy-initialized on first embed call

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(vertexai=True, project=self._project, location=self._location)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types as gtypes

        client = self._get_client()
        result: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = client.models.embed_content(
                model=self._model,
                contents=batch,
                config=gtypes.EmbedContentConfig(output_dimensionality=768),
            )
            for emb in response.embeddings:
                result.append(emb.values)
        return result


def get_default_embedder(
    project: str | None = None,
    location: str = "us-central1",
) -> VertexEmbedder:
    return VertexEmbedder(project=project, location=location)
