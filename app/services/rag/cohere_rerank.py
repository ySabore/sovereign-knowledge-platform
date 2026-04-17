"""Hosted cross-encoder rerank via Cohere Rerank API (optional; falls back in pipeline)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.services.field_encryption import decrypt_org_secret
from app.services.rag.types import RetrievalHit

if TYPE_CHECKING:
    from app.models import Organization

logger = logging.getLogger(__name__)

_COHERE_RERANK_URL = "https://api.cohere.com/v1/rerank"


def resolve_cohere_api_key(org: Organization | None) -> str | None:
    """Prefer per-organization encrypted key; fall back to platform ``COHERE_API_KEY``."""
    if org is not None and (org.cohere_api_key_encrypted or "").strip():
        try:
            decrypted = decrypt_org_secret(org.cohere_api_key_encrypted)
        except (RuntimeError, ValueError) as exc:
            logger.warning("Could not decrypt organization Cohere API key: %s", exc)
            return None
        if decrypted and str(decrypted).strip():
            return str(decrypted).strip()
    sk = (settings.cohere_api_key or "").strip()
    return sk or None


def cohere_rerank_configured(org: Organization | None = None) -> bool:
    return bool(resolve_cohere_api_key(org))


def apply_cohere_rerank(
    query: str,
    hits: list[RetrievalHit],
    *,
    top_n: int,
    org: Organization | None = None,
) -> list[RetrievalHit] | None:
    """
    Re-order ``hits`` using Cohere Rerank. Returns ``None`` if misconfigured, empty query, or HTTP/API error.
    """
    api_key = resolve_cohere_api_key(org)
    if not api_key:
        return None
    q = (query or "").strip()
    if not hits or not q:
        return hits if not q else None

    max_chars = settings.cohere_rerank_max_chars_per_doc
    texts = [(h.content or "")[:max_chars] for h in hits]
    timeout = settings.cohere_rerank_timeout_seconds

    payload = {
        "model": settings.cohere_rerank_model,
        "query": q,
        "documents": texts,
        "top_n": min(top_n, len(texts)),
        "return_documents": False,
    }
    try:
        response = httpx.post(
            _COHERE_RERANK_URL,
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Cohere rerank request failed: %s", exc)
        return None

    results = body.get("results") or []
    if not results:
        return None

    out: list[RetrievalHit] = []
    for item in results:
        try:
            idx = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(hits):
            continue
        score_raw = item.get("relevance_score")
        try:
            score = float(score_raw) if score_raw is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        score = min(1.0, max(0.0, score))
        out.append(replace(hits[idx], score=score))

    return out if out else None
