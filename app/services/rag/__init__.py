"""Modular RAG layer: retrieval, heuristic rerank, prompt helpers, and pipeline orchestration."""

from app.services.rag.answer_parse import estimate_tokens, extract_confidence_tag
from app.services.rag.heuristic_rerank import apply_heuristic_rerank, lexical_overlap_score
from app.services.rag.pipeline import run_retrieval_pipeline
from app.services.rag.prompts import (
    build_ollama_grounded_prompt,
    format_evidence_lines_for_prompt,
    trim_conversation_turns_for_prompt,
)
from app.services.rag.retrieval import (
    effective_retrieval_strategy,
    embed_query_text,
    resolve_top_k,
    retrieve_workspace_chunks,
    retrieve_workspace_chunks_hybrid,
)
from app.services.rag.summary import build_grounded_answer
from app.services.rag.types import RetrievalHit

__all__ = [
    "RetrievalHit",
    "apply_heuristic_rerank",
    "build_grounded_answer",
    "build_ollama_grounded_prompt",
    "effective_retrieval_strategy",
    "embed_query_text",
    "estimate_tokens",
    "extract_confidence_tag",
    "format_evidence_lines_for_prompt",
    "lexical_overlap_score",
    "resolve_top_k",
    "retrieve_workspace_chunks",
    "retrieve_workspace_chunks_hybrid",
    "run_retrieval_pipeline",
    "trim_conversation_turns_for_prompt",
]
