from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class RetrievalHit:
    """One chunk returned from vector retrieval (and optionally re-ordered by heuristic reranking)."""

    chunk_id: UUID
    document_id: UUID
    document_filename: str
    chunk_index: int
    page_number: int | None
    score: float
    content: str
