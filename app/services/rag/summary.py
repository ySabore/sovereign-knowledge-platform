from __future__ import annotations

from app.services.rag.types import RetrievalHit


def build_grounded_answer(query: str, hits: list[RetrievalHit]) -> str:
    """Short human-readable summary of retrieval for the document search API (not the LLM system prompt)."""
    if not hits:
        return (
            "I could not find indexed document context for that question in this workspace yet. "
            "Upload and index documents, or verify the embedding service is available."
        )

    excerpt_lines: list[str] = []
    for hit in hits[: min(len(hits), 3)]:
        page_suffix = f" (page {hit.page_number})" if hit.page_number is not None else ""
        excerpt_lines.append(f"- {hit.document_filename}{page_suffix}: {hit.content[:280]}")

    return (
        f"Grounded retrieval summary for: {query}\n"
        + "\n".join(excerpt_lines)
        + "\nUse these retrieved passages as the citation-ready context for the next answer-generation step."
    )
