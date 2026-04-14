from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk
from app.services.embeddings import get_embedding_client

from app.services.rag.types import RetrievalHit


def embed_query_text(query: str) -> list[float]:
    client = get_embedding_client()
    return client.embed_texts([query])[0]


def retrieve_workspace_chunks(
    db: Session,
    *,
    workspace_id: UUID,
    query_embedding: list[float],
    top_k: int,
    allowed_document_ids: set[UUID] | None = None,
) -> list[RetrievalHit]:
    """Vector search: cosine distance over chunk embeddings, workspace-scoped.

    When ``allowed_document_ids`` is provided (RBAC), restrict chunks to those documents.
    Empty set ⇒ no results (caller should short-circuit before query when possible).
    """
    if allowed_document_ids is not None and len(allowed_document_ids) == 0:
        return []

    distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            Document.filename,
            DocumentChunk.chunk_index,
            DocumentChunk.page_number,
            DocumentChunk.content,
            distance_expr.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.workspace_id == workspace_id, DocumentChunk.embedding.is_not(None))
    )
    if allowed_document_ids is not None:
        stmt = stmt.where(Document.id.in_(allowed_document_ids))
    stmt = stmt.order_by(distance_expr.asc(), DocumentChunk.chunk_index.asc()).limit(top_k)

    rows = db.execute(stmt).all()
    return [
        RetrievalHit(
            chunk_id=row[0],
            document_id=row[1],
            document_filename=row[2],
            chunk_index=row[3],
            page_number=row[4],
            content=row[5],
            score=max(0.0, 1.0 - float(row[6])),
        )
        for row in rows
    ]


def resolve_top_k(requested_top_k: int | None) -> int:
    if requested_top_k is None:
        return settings.retrieval_top_k
    return requested_top_k
