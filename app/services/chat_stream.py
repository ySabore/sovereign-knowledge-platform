"""Streaming assistant responses (SSE) — same RAG path as non-streaming chat."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.models import Organization
from app.services.chat import (
    FALLBACK_NO_EVIDENCE,
    AnswerGenerationError,
    Citation,
    _answer_references_available_citations,
    _deterministic_cap_answer_override,
    _deterministic_policy_answer,
    _deterministic_role_scope_answer,
    _generate_extractive_answer,
    _grounded_prompt_text,
    _likely_permission_contradiction,
    _postprocess_grounded_rbac,
    build_citations_for_query,
    generation_model_for_mode,
    has_sufficient_evidence,
    preferred_chat_model_from_org,
)
from app.services.llm.cloud_chat import stream_anthropic_chat_tokens, stream_openai_chat_tokens
from app.services.org_chat_credentials import (
    ollama_base_url_for_org,
    resolve_anthropic_for_org,
    resolve_openai_for_org,
)
from app.services.rag.answer_parse import extract_confidence_tag
from app.services.rag.types import RetrievalHit

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def confidence_label_from_hits(hits: list[RetrievalHit]) -> str:
    if not hits:
        return "low"
    top = [float(h.score) for h in hits[:3]]
    s1 = top[0]
    s2 = top[1] if len(top) > 1 else 0.0
    avg = sum(top) / len(top)
    strong_count = sum(1 for x in top if x >= 0.35)
    # High confidence: strong lead hit or strong support across multiple top chunks.
    if s1 >= 0.72 or (s1 >= 0.58 and s2 >= 0.48) or (avg >= 0.48 and strong_count >= 2):
        return "high"
    # Medium confidence: usable lead hit or consistent moderate support.
    if s1 >= 0.36 or (avg >= 0.28 and strong_count >= 2):
        return "medium"
    return "low"


def _token_chunks(text: str) -> list[str]:
    return re.findall(r"\S+\s*", text, flags=re.DOTALL)


async def _iter_ollama_token_stream(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    org: Organization | None = None,
) -> AsyncIterator[str]:
    prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)

    url = f"{ollama_base_url_for_org(org)}/api/generate"
    model = preferred_chat_model_from_org(org) or settings.answer_generation_model
    body = {
        "model": model,
        "prompt": prompt,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=settings.ollama_http_timeout_seconds) as client:
        async with client.stream("POST", url, json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("response"):
                    yield obj["response"]
                if obj.get("done"):
                    break


async def _yield_post_generative_stream(
    query: str,
    citations: list[Citation],
    hits: list[RetrievalHit],
    *,
    answer: str,
    ok_mode: str,
    fallback_mode: str,
    preferred_chat_model: str | None,
    hit_contents: list[str],
) -> AsyncIterator[dict[str, Any]]:
    if not answer:
        raise AnswerGenerationError("LLM answer generation returned an empty response")
    display, conf_from_tag = extract_confidence_tag(answer)
    if display == FALLBACK_NO_EVIDENCE:
        yield {
            "kind": "done",
            "citations": [],
            "confidence": "low",
            "full_text": display,
            "generation_mode": "no_evidence",
            "generation_model": generation_model_for_mode("no_evidence"),
        }
        return
    if not _answer_references_available_citations(display, citation_count=len(citations)):
        policy_fix = _deterministic_policy_answer(query=query, citations=citations, hit_contents=hit_contents)
        if policy_fix is not None:
            full_text = policy_fix[0]
            cits = [c.to_dict() for c in citations]
        else:
            full_text, cits = _generate_extractive_answer(query, citations)
        yield {"kind": "token", "text": "\n\n"}
        for chunk in _token_chunks(full_text):
            yield {"kind": "token", "text": chunk}
        yield {
            "kind": "done",
            "citations": cits,
            "confidence": confidence_label_from_hits(hits),
            "full_text": full_text,
            "generation_mode": fallback_mode,
            "generation_model": generation_model_for_mode(
                fallback_mode, preferred_chat_model=preferred_chat_model
            ),
        }
        return
    if _likely_permission_contradiction(query=query, answer=display, citations=citations):
        policy_fix = _deterministic_policy_answer(query=query, citations=citations, hit_contents=hit_contents)
        if policy_fix is not None:
            full_text = policy_fix[0]
            cits = [c.to_dict() for c in citations]
        else:
            full_text, cits = _generate_extractive_answer(query, citations)
        yield {"kind": "token", "text": "\n\n"}
        for chunk in _token_chunks(full_text):
            yield {"kind": "token", "text": chunk}
        yield {
            "kind": "done",
            "citations": cits,
            "confidence": confidence_label_from_hits(hits),
            "full_text": full_text,
            "generation_mode": fallback_mode,
            "generation_model": generation_model_for_mode(
                fallback_mode, preferred_chat_model=preferred_chat_model
            ),
        }
        return
    policy_fix = _deterministic_policy_answer(query=query, citations=citations, hit_contents=hit_contents)
    cap_override = _deterministic_cap_answer_override(query, display, policy_fix)
    if cap_override is not None:
        full_text = cap_override
        cits = [c.to_dict() for c in citations]
        yield {"kind": "token", "text": "\n\n"}
        for chunk in _token_chunks(full_text):
            yield {"kind": "token", "text": chunk}
        yield {
            "kind": "done",
            "citations": cits,
            "confidence": confidence_label_from_hits(hits),
            "full_text": full_text,
            "generation_mode": fallback_mode,
            "generation_model": generation_model_for_mode(
                fallback_mode, preferred_chat_model=preferred_chat_model
            ),
        }
        return
    final_conf = conf_from_tag if conf_from_tag else confidence_label_from_hits(hits)
    display = _postprocess_grounded_rbac(query, display, citations, hit_contents)
    yield {
        "kind": "done",
        "citations": [c.to_dict() for c in citations],
        "confidence": final_conf,
        "full_text": display,
        "generation_mode": ok_mode,
        "generation_model": generation_model_for_mode(ok_mode, preferred_chat_model=preferred_chat_model),
    }


async def stream_grounded_answer_events(
    query: str,
    hits: list[RetrievalHit],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    answer_provider: str | None = None,
    org: Organization | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Yields dict events:
      { "kind": "token", "text": str }
      { "kind": "done", "citations": [...], "confidence": str, "full_text": str }
    """
    citations = build_citations_for_query(hits, query=query)
    hit_contents = [h.content for h in hits[: len(citations)]]
    provider = (answer_provider or settings.answer_generation_provider).lower().strip()
    if not citations or not has_sufficient_evidence(hits, query=query):
        yield {"kind": "token", "text": FALLBACK_NO_EVIDENCE}
        yield {
            "kind": "done",
            "citations": [],
            "confidence": "low",
            "full_text": FALLBACK_NO_EVIDENCE,
            "generation_mode": "no_evidence",
            "generation_model": generation_model_for_mode("no_evidence"),
        }
        return

    role_scope = _deterministic_role_scope_answer(query, hit_contents, citations)
    if role_scope is not None:
        short_mode = (
            "openai"
            if provider == "openai"
            else "anthropic"
            if provider == "anthropic"
            else "ollama"
            if provider == "ollama"
            else "extractive"
        )
        for chunk in _token_chunks(role_scope):
            yield {"kind": "token", "text": chunk}
        yield {
            "kind": "done",
            "citations": [c.to_dict() for c in citations],
            "confidence": confidence_label_from_hits(hits),
            "full_text": role_scope,
            "generation_mode": short_mode,
            "generation_model": generation_model_for_mode(short_mode, preferred_chat_model=preferred_chat_model_from_org(org)),
        }
        return
    if provider == "extractive":
        full_text, cits = _generate_extractive_answer(query, citations)
        for chunk in _token_chunks(full_text):
            yield {"kind": "token", "text": chunk}
        yield {
            "kind": "done",
            "citations": cits,
            "confidence": confidence_label_from_hits(hits),
            "full_text": full_text,
            "generation_mode": "extractive",
            "generation_model": generation_model_for_mode("extractive"),
        }
        return

    preferred = preferred_chat_model_from_org(org)

    if provider == "ollama":
        pieces: list[str] = []
        try:
            async for piece in _iter_ollama_token_stream(
                query, citations, conversation_turns=conversation_turns, org=org
            ):
                pieces.append(piece)
                yield {"kind": "token", "text": piece}
        except httpx.HTTPError as exc:
            raise AnswerGenerationError(f"Ollama answer generation failed: {exc}") from exc

        answer = "".join(pieces).strip()
        async for ev in _yield_post_generative_stream(
            query,
            citations,
            hits,
            answer=answer,
            ok_mode="ollama",
            fallback_mode="ollama_fallback_extractive",
            preferred_chat_model=preferred,
            hit_contents=hit_contents,
        ):
            yield ev
        return

    if provider == "openai":
        pieces: list[str] = []
        try:
            api_key, model, base = resolve_openai_for_org(org)
        except RuntimeError as exc:
            raise AnswerGenerationError(str(exc)) from exc
        prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)
        try:
            async for piece in stream_openai_chat_tokens(
                api_key=api_key, base_url=base, model=model, user_prompt=prompt
            ):
                pieces.append(piece)
                yield {"kind": "token", "text": piece}
        except httpx.HTTPError as exc:
            raise AnswerGenerationError(f"OpenAI answer generation failed: {exc}") from exc

        answer = "".join(pieces).strip()
        async for ev in _yield_post_generative_stream(
            query,
            citations,
            hits,
            answer=answer,
            ok_mode="openai",
            fallback_mode="openai_fallback_extractive",
            preferred_chat_model=preferred,
            hit_contents=hit_contents,
        ):
            yield ev
        return

    if provider == "anthropic":
        pieces: list[str] = []
        try:
            api_key, model, base = resolve_anthropic_for_org(org)
        except RuntimeError as exc:
            raise AnswerGenerationError(str(exc)) from exc
        prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)
        try:
            async for piece in stream_anthropic_chat_tokens(
                api_key=api_key, base_url=base, model=model, user_prompt=prompt
            ):
                pieces.append(piece)
                yield {"kind": "token", "text": piece}
        except httpx.HTTPError as exc:
            raise AnswerGenerationError(f"Anthropic answer generation failed: {exc}") from exc

        answer = "".join(pieces).strip()
        async for ev in _yield_post_generative_stream(
            query,
            citations,
            hits,
            answer=answer,
            ok_mode="anthropic",
            fallback_mode="anthropic_fallback_extractive",
            preferred_chat_model=preferred,
            hit_contents=hit_contents,
        ):
            yield ev
        return

    raise AnswerGenerationError(f"Unsupported answer generation provider: {provider}")
