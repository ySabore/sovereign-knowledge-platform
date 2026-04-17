"""Reciprocal Rank Fusion (RRF) for merging ranked retrieval lists."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from app.services.rag.types import RetrievalHit


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalHit]],
    *,
    k: int = 60,
) -> list[RetrievalHit]:
    """
    Merge multiple ordered hit lists into one ranked list.

    RRF score for a chunk = sum_i 1/(k + rank_i) across lists where it appears.
    """
    if not ranked_lists:
        return []
    scores: dict[UUID, float] = {}
    best: dict[UUID, RetrievalHit] = {}
    for hits in ranked_lists:
        if not hits:
            continue
        for rank, hit in enumerate(hits, start=1):
            cid = hit.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in best:
                best[cid] = hit
    if not scores:
        return []
    ordered_ids = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)
    return [replace(best[cid], score=scores[cid]) for cid in ordered_ids]
