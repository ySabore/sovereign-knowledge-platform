"""
Heuristic re-ranking without extra ML models: lexical overlap with the query plus optional MMR diversity.

Uses token Jaccard similarity only (no cross-encoder, no second embedding model).
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.config import settings

from app.services.rag.types import RetrievalHit

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text) if len(m.group(0)) > 2}


def lexical_overlap_score(query: str, chunk_text: str) -> float:
    """Token Jaccard overlap in [0, 1] between query and chunk."""
    q, c = _tokens(query), _tokens(chunk_text)
    if not q or not c:
        return 0.0
    inter = len(q & c)
    union = len(q | c)
    return inter / union if union else 0.0


def _chunk_lexical_similarity(a: str, b: str) -> float:
    """Diversity term: how similar two chunks are (used in MMR)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _blended_score(semantic: float, lexical: float) -> float:
    w = settings.rag_lexical_weight
    return (1.0 - w) * semantic + w * lexical


def apply_heuristic_rerank(
    query: str,
    hits: list[RetrievalHit],
    *,
    output_top_k: int,
) -> list[RetrievalHit]:
    """
    Re-rank or trim retrieval hits. Modes (see `settings.rag_rerank_mode`):

    - none: first-pass vector order, truncated to output_top_k
    - lexical_blend: sort by blended semantic + lexical relevance
    - lexical_mmr: MMR selection using blended relevance and lexical diversity between chunks
    """
    if not hits:
        return []

    mode = settings.rag_rerank_mode.strip().lower()
    k = min(output_top_k, len(hits))

    if mode == "none":
        return hits[:k]

    lex_scores = [lexical_overlap_score(query, h.content) for h in hits]
    blended = [_blended_score(h.score, lx) for h, lx in zip(hits, lex_scores, strict=True)]

    if mode == "lexical_blend":
        order = sorted(range(len(hits)), key=lambda i: blended[i], reverse=True)
        return [
            replace(hits[i], score=round(blended[i], 6))
            for i in order[:k]
        ]

    if mode == "lexical_mmr":
        lam = settings.rag_mmr_lambda
        remaining = set(range(len(hits)))
        selected: list[int] = []

        while len(selected) < k and remaining:
            best_i: int | None = None
            best_mmr = float("-inf")
            for i in remaining:
                rel = blended[i]
                if not selected:
                    mmr = rel
                else:
                    max_sim = max(_chunk_lexical_similarity(hits[i].content, hits[j].content) for j in selected)
                    mmr = lam * rel - (1.0 - lam) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_i = i
            assert best_i is not None
            selected.append(best_i)
            remaining.discard(best_i)

        return [replace(hits[i], score=round(blended[i], 6)) for i in selected]

    # Unknown mode: behave like none
    return hits[:k]
