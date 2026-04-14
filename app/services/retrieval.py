"""Backward-compatible facade for the modular RAG package (`app.services.rag`)."""

from __future__ import annotations

from app.services.rag import (
    RetrievalHit,
    apply_heuristic_rerank,
    build_grounded_answer,
    embed_query_text,
    resolve_top_k,
    retrieve_workspace_chunks,
    run_retrieval_pipeline,
)

__all__ = [
    "RetrievalHit",
    "apply_heuristic_rerank",
    "build_grounded_answer",
    "embed_query_text",
    "resolve_top_k",
    "retrieve_workspace_chunks",
    "run_retrieval_pipeline",
]
