"""
RAG workflow orchestration: embed query → retrieve → heuristic rerank.

Retrieval mode per organization: **heuristic** (vector only, then lexical/MMR rerank) or **hybrid**
(vector + Postgres FTS on ``content_tsv``, merged with RRF). Chat and document search both use
``run_retrieval_pipeline`` so behavior stays aligned.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, User
from app.services.permissions import filter_chunks_by_permission, get_accessible_document_ids
from app.services.rag.cohere_rerank import apply_cohere_rerank, cohere_rerank_configured
from app.services.rag.heuristic_rerank import apply_heuristic_rerank
from app.services.rag.query_normalize import normalize_for_retrieval
from app.services.rag.retrieval import (
    effective_retrieval_strategy,
    embed_query_text,
    resolve_top_k,
    retrieve_workspace_chunks,
    retrieve_workspace_chunks_hybrid,
)
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
    org: Organization | None = None,
) -> list[RetrievalHit]:
    """
    Full retrieval stage for one user query: embedding, over-fetch, rerank, RBAC filter.

    1. Resolve accessible documents (simple vs full RBAC).
    2. Embed the query (embedding model).
    3. Pull ``retrieval_candidate_k`` chunks: vector-only, hybrid (vector + FTS + RRF), or vector-only when strategy is ``rerank``.
    4. Cohere hosted rerank and/or heuristic rerank to ``top_k`` (see org ``retrieval_strategy`` / ``use_hosted_rerank``).
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
    strategy = effective_retrieval_strategy(org)
    if strategy == "hybrid":
        raw_hits = retrieve_workspace_chunks_hybrid(
            db,
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            query_text=rq,
            candidate_k=candidate_k,
            allowed_document_ids=allowed,
            rrf_k=settings.rrf_k,
        )
    else:
        # heuristic and rerank both use vector retrieval for the candidate pool
        raw_hits = retrieve_workspace_chunks(
            db,
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=candidate_k,
            allowed_document_ids=allowed,
        )

    want_cohere = cohere_rerank_configured(org) and (
        strategy == "rerank" or (org is not None and org.use_hosted_rerank)
    )
    if want_cohere:
        cohere_hits = apply_cohere_rerank(rq, raw_hits, top_n=top_k, org=org)
        ranked = (
            cohere_hits
            if cohere_hits is not None
            else apply_heuristic_rerank(rq, raw_hits, output_top_k=top_k)
        )
    else:
        ranked = apply_heuristic_rerank(rq, raw_hits, output_top_k=top_k)
    return filter_chunks_by_permission(
        db,
        ranked,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user=user,
    )
