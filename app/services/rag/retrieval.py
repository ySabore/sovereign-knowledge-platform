from __future__ import annotations

from uuid import UUID

from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk, Organization
from app.services.embeddings import get_embedding_client

from app.services.rag.rrf import reciprocal_rank_fusion
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


def retrieve_workspace_chunks_fts(
    db: Session,
    *,
    workspace_id: UUID,
    query_text: str,
    top_k: int,
    allowed_document_ids: set[UUID] | None = None,
) -> list[RetrievalHit]:
    """
    Keyword search over chunk text using Postgres ``content_tsv`` (GIN) + ``plainto_tsquery``.

    Requires migration ``012_retrieval_hybrid_fts`` (generated ``content_tsv`` column).
    """
    if allowed_document_ids is not None and len(allowed_document_ids) == 0:
        return []
    q = (query_text or "").strip()
    if not q:
        return []

    base_sql = """
SELECT dc.id, dc.document_id, d.filename, dc.chunk_index, dc.page_number, dc.content,
       ts_rank_cd(dc.content_tsv, plainto_tsquery('english', :q)) AS trank
FROM document_chunks dc
INNER JOIN documents d ON d.id = dc.document_id
WHERE d.workspace_id = CAST(:ws AS uuid)
  AND dc.embedding IS NOT NULL
  AND dc.content_tsv @@ plainto_tsquery('english', :q)
"""
    if allowed_document_ids is not None:
        stmt = (
            text(
                base_sql
                + " AND d.id = ANY(:doc_ids)\n"
                + "ORDER BY trank DESC NULLS LAST, dc.chunk_index ASC\n"
                + "LIMIT :lim"
            ).bindparams(bindparam("doc_ids", type_=ARRAY(PG_UUID(as_uuid=True))))
        )
        params: dict = {
            "q": q,
            "ws": str(workspace_id),
            "lim": top_k,
            "doc_ids": list(allowed_document_ids),
        }
    else:
        stmt = text(base_sql + "ORDER BY trank DESC NULLS LAST, dc.chunk_index ASC\nLIMIT :lim")
        params = {"q": q, "ws": str(workspace_id), "lim": top_k}

    rows = db.execute(stmt, params).all()
    out: list[RetrievalHit] = []
    for row in rows:
        # SQL selects 7 columns (0..6); use named access to avoid index drift.
        trank_raw = row._mapping.get("trank")
        trank = float(trank_raw) if trank_raw is not None else 0.0
        out.append(
            RetrievalHit(
                chunk_id=row[0],
                document_id=row[1],
                document_filename=row[2],
                chunk_index=row[3],
                page_number=row[4],
                content=row[5],
                score=min(1.0, max(0.0, trank)),
            )
        )
    return out


def retrieve_workspace_chunks_hybrid(
    db: Session,
    *,
    workspace_id: UUID,
    query_embedding: list[float],
    query_text: str,
    candidate_k: int,
    allowed_document_ids: set[UUID] | None,
    rrf_k: int,
) -> list[RetrievalHit]:
    """
    Vector top-``candidate_k`` + keyword top-``candidate_k``, merged via RRF, then truncated to ``candidate_k``.
    """
    vec = retrieve_workspace_chunks(
        db,
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        top_k=candidate_k,
        allowed_document_ids=allowed_document_ids,
    )
    fts = retrieve_workspace_chunks_fts(
        db,
        workspace_id=workspace_id,
        query_text=query_text,
        top_k=candidate_k,
        allowed_document_ids=allowed_document_ids,
    )
    if not vec and not fts:
        return []
    if not fts:
        return vec
    if not vec:
        return fts
    merged = reciprocal_rank_fusion([vec, fts], k=rrf_k)
    return merged[:candidate_k]


def effective_retrieval_strategy(org: Organization | None) -> str:
    """
    Resolve fetch + rerank mode: ``heuristic`` (vector candidates), ``hybrid`` (vector + FTS + RRF),
    or ``rerank`` (vector candidates only; final order via Cohere when configured, else lexical heuristic).
    """
    raw = ""
    if org and org.retrieval_strategy:
        raw = str(org.retrieval_strategy).strip()
    if not raw:
        raw = (settings.retrieval_strategy_default or "heuristic").strip()
    s = raw.lower()
    if s == "rerank":
        return "rerank"
    if s == "hybrid":
        return "hybrid"
    return "heuristic"


def resolve_top_k(requested_top_k: int | None) -> int:
    if requested_top_k is None:
        return settings.retrieval_top_k
    return requested_top_k
