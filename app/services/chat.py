from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import settings
from app.models import Organization
from app.services.llm.cloud_chat import complete_anthropic_chat, complete_openai_chat
from app.services.org_chat_credentials import resolve_anthropic_for_org, resolve_openai_for_org
from app.services.rag.answer_parse import extract_confidence_tag
from app.services.rag.heuristic_rerank import lexical_overlap_score
from app.services.rag.prompts import build_ollama_grounded_prompt, format_evidence_lines_for_prompt
from app.services.rag.query_normalize import normalize_for_retrieval
from app.services.rag.types import RetrievalHit

FALLBACK_NO_EVIDENCE = "I don't know based on the documents in this workspace."
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
GenerationMode = Literal[
    "ollama",
    "ollama_fallback_extractive",
    "openai",
    "openai_fallback_extractive",
    "anthropic",
    "anthropic_fallback_extractive",
    "extractive",
    "no_evidence",
    "chitchat",
]


class AnswerGenerationError(RuntimeError):
    """Raised when configured answer generation fails."""


@dataclass(slots=True)
class Citation:
    chunk_id: str
    document_id: str
    document_filename: str
    chunk_index: int
    page_number: int | None
    score: float
    quote: str

    def to_dict(self) -> dict[str, str | int | float | None]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "score": round(self.score, 4),
            "quote": self.quote,
        }


def build_citations(hits: list[RetrievalHit], *, limit: int = 3) -> list[Citation]:
    citations: list[Citation] = []
    for hit in hits[:limit]:
        citations.append(
            Citation(
                chunk_id=str(hit.chunk_id),
                document_id=str(hit.document_id),
                document_filename=hit.document_filename,
                chunk_index=hit.chunk_index,
                page_number=hit.page_number,
                score=hit.score,
                quote=hit.content[: settings.chat_citation_quote_max_chars],
            )
        )
    return citations


def has_sufficient_evidence(hits: list[RetrievalHit], *, query: str = "") -> bool:
    if not hits:
        return False
    # After heuristic rerank, scores are blended (semantic + lexical); the first row is not always
    # the strongest semantic hit. Accept if any of the top few clears the bar.
    cap = min(3, len(hits))
    threshold = settings.chat_min_citation_score
    if any(hits[i].score >= threshold for i in range(cap)):
        return True
    # Embedding + blend can under-score good keyword overlap; allow strong lexical match on top hits.
    q = normalize_for_retrieval(query).strip()
    if not q:
        return False
    lex_min = settings.chat_lexical_overlap_min
    return any(lexical_overlap_score(q, hits[i].content) >= lex_min for i in range(cap))


def preferred_chat_model_from_org(org: Organization | None) -> str | None:
    if org and org.preferred_chat_model and str(org.preferred_chat_model).strip():
        return str(org.preferred_chat_model).strip()
    return None


def _grounded_prompt_text(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
) -> str:
    payload = [
        (
            citation.document_filename,
            str(citation.page_number) if citation.page_number is not None else None,
            citation.quote,
        )
        for citation in citations
    ]
    evidence_lines = format_evidence_lines_for_prompt(payload)
    return build_ollama_grounded_prompt(
        query=query,
        evidence_lines=evidence_lines,
        fallback_exact=FALLBACK_NO_EVIDENCE,
        conversation_turns=conversation_turns,
    )


def _finalize_generative_answer(
    query: str,
    citations: list[Citation],
    raw: str,
    *,
    ok_mode: GenerationMode,
    fallback_mode: GenerationMode,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    text = (raw or "").strip()
    if not text:
        raise AnswerGenerationError("LLM returned an empty response")
    display, _conf_tag = extract_confidence_tag(text)
    if display == FALLBACK_NO_EVIDENCE:
        return FALLBACK_NO_EVIDENCE, [], "no_evidence"
    if not _answer_references_available_citations(display, citation_count=len(citations)):
        answer, cits = _generate_extractive_answer(query, citations)
        return answer, cits, fallback_mode
    return display, [citation.to_dict() for citation in citations], ok_mode


def generate_grounded_answer(
    query: str,
    hits: list[RetrievalHit],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    answer_provider: str | None = None,
    org: Organization | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    citations = build_citations(hits)
    if not citations or not has_sufficient_evidence(hits, query=query):
        return FALLBACK_NO_EVIDENCE, [], "no_evidence"

    provider = (answer_provider or settings.answer_generation_provider).lower().strip()
    if provider == "extractive":
        answer, cits = _generate_extractive_answer(query, citations)
        return answer, cits, "extractive"
    if provider == "ollama":
        return _generate_ollama_answer(query, citations, conversation_turns=conversation_turns, org=org)
    if provider == "openai":
        return _generate_openai_answer(query, citations, conversation_turns=conversation_turns, org=org)
    if provider == "anthropic":
        return _generate_anthropic_answer(query, citations, conversation_turns=conversation_turns, org=org)
    raise AnswerGenerationError(f"Unsupported answer generation provider: {provider}")


def _generate_extractive_answer(query: str, citations: list[Citation]) -> tuple[str, list[dict[str, str | int | float | None]]]:
    bullets: list[str] = []
    for idx, citation in enumerate(citations, start=1):
        page = f", page {citation.page_number}" if citation.page_number is not None else ""
        bullets.append(
            f"[{idx}] {citation.document_filename}{page}: {citation.quote}"
        )

    answer = (
        f"Answer grounded in retrieved workspace documents for: {query}\n"
        + "\n".join(bullets)
    )
    return answer, [citation.to_dict() for citation in citations]


def _generate_ollama_answer(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    org: Organization | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)
    model = preferred_chat_model_from_org(org) or settings.answer_generation_model
    try:
        response = httpx.post(
            f"{settings.answer_generation_ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=settings.ollama_http_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AnswerGenerationError(f"Ollama answer generation failed: {exc}") from exc

    body = response.json()
    answer = (body.get("response") or "").strip()
    return _finalize_generative_answer(
        query, citations, answer, ok_mode="ollama", fallback_mode="ollama_fallback_extractive"
    )


def _generate_openai_answer(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    org: Organization | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    try:
        api_key, _model, base = resolve_openai_for_org(org)
    except RuntimeError as exc:
        raise AnswerGenerationError(str(exc)) from exc
    prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)
    try:
        answer = complete_openai_chat(api_key=api_key, base_url=base, model=_model, user_prompt=prompt)
    except RuntimeError as exc:
        raise AnswerGenerationError(str(exc)) from exc
    return _finalize_generative_answer(
        query, citations, answer, ok_mode="openai", fallback_mode="openai_fallback_extractive"
    )


def _generate_anthropic_answer(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    org: Organization | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    try:
        api_key, _model, base = resolve_anthropic_for_org(org)
    except RuntimeError as exc:
        raise AnswerGenerationError(str(exc)) from exc
    prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)
    try:
        answer = complete_anthropic_chat(api_key=api_key, base_url=base, model=_model, user_prompt=prompt)
    except RuntimeError as exc:
        raise AnswerGenerationError(str(exc)) from exc
    return _finalize_generative_answer(
        query,
        citations,
        answer,
        ok_mode="anthropic",
        fallback_mode="anthropic_fallback_extractive",
    )


def _answer_references_available_citations(answer: str, *, citation_count: int) -> bool:
    if citation_count <= 0:
        return False

    matches = [int(match) for match in _CITATION_PATTERN.findall(answer)]
    if not matches:
        return False
    return all(1 <= match <= citation_count for match in matches)


def generation_model_for_mode(
    mode: GenerationMode,
    *,
    preferred_chat_model: str | None = None,
) -> str | None:
    """Model label to expose in debug payloads."""
    chip = (preferred_chat_model or "").strip()
    if mode in ("ollama", "ollama_fallback_extractive"):
        return chip or settings.answer_generation_model
    if mode in ("openai", "openai_fallback_extractive"):
        return chip or settings.openai_default_chat_model
    if mode in ("anthropic", "anthropic_fallback_extractive"):
        return chip or settings.anthropic_default_chat_model
    if mode == "extractive":
        return "extractive"
    if mode == "chitchat":
        return None
    return None
