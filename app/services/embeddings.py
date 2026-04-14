from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings


class EmbeddingServiceError(RuntimeError):
    pass


class OllamaEmbeddingClient:
    def __init__(self, *, base_url: str, model: str, timeout_seconds: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {"model": self.model, "input": texts}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/api/embed", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError(f"Embedding request failed against Ollama: {exc}") from exc

        data: dict[str, Any] = response.json()
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingServiceError("Ollama returned an invalid embeddings payload")

        normalized: list[list[float]] = []
        for embedding in embeddings:
            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingServiceError("Ollama returned an empty embedding vector")
            normalized.append([float(value) for value in embedding])
        return normalized

    def embed_texts_batched(
        self,
        texts: list[str],
        *,
        batch_size: int | None = None,
        delay_seconds: float | None = None,
    ) -> list[list[float]]:
        """Batch requests (OpenAI-style rate limiting) — Ollama accepts batch `input` arrays."""
        if not texts:
            return []
        bs = batch_size if batch_size is not None else settings.embedding_batch_size
        delay = settings.embedding_batch_delay_seconds if delay_seconds is None else delay_seconds
        out: list[list[float]] = []
        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            out.extend(self.embed_texts(batch))
            if delay > 0 and i + bs < len(texts):
                time.sleep(delay)
        return out


def get_embedding_client() -> OllamaEmbeddingClient:
    provider = settings.embedding_provider.strip().lower()
    if provider != "ollama":
        raise EmbeddingServiceError(f"Unsupported embedding provider: {settings.embedding_provider}")
    return OllamaEmbeddingClient(
        base_url=settings.embedding_ollama_base_url,
        model=settings.embedding_model,
        timeout_seconds=settings.ollama_http_timeout_seconds,
    )
