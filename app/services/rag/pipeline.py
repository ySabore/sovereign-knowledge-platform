"""
RAG workflow orchestration: embed query → vector retrieve → heuristic rerank.

Chat and document search both use `run_retrieval_pipeline` so behavior stays aligned.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.services.permissions import filter_chunks_by_permission, get_accessible_document_ids
from app.services.rag.heuristic_rerank import apply_heuristic_rerank
from app.services.rag.query_normalize import normalize_for_retrieval
from app.services.rag.retrieval import embed_query_text, resolve_top_k, retrieve_workspace_chunks
from app.services.rag.types import RetrievalHit


def run_retrieval_pipeline(
    db: Session,
    *,
    workspace_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    user: User | None,
    query: str,
    requested_top_k: int | None,
) -> list[RetrievalHit]:
    """
    Full retrieval stage for one user query: embedding, over-fetch, rerank, RBAC filter.

    1. Resolve accessible documents (simple vs full RBAC).
    2. Embed the query (embedding model).
    3. Pull `retrieval_candidate_k` nearest chunks within allowed documents.
    4. Heuristic rerank / diversify to `top_k`.
    5. Post-filter chunks (failsafe).
    """
    top_k = resolve_top_k(requested_top_k)
    candidate_k = max(top_k, min(settings.retrieval_candidate_k, 50))

    allowed = get_accessible_document_ids(
        db,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user=user,
    )
    if settings.rbac_mode.strip().lower() == "full" and not allowed:
        return []

    rq = normalize_for_retrieval(query)
    query_embedding = embed_query_text(rq)
    raw_hits = retrieve_workspace_chunks(
        db,
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        top_k=candidate_k,
        allowed_document_ids=allowed,
    )
    ranked = apply_heuristic_rerank(rq, raw_hits, output_top_k=top_k)
    return filter_chunks_by_permission(
        db,
        ranked,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user=user,
    )
