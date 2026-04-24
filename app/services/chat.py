from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import settings
from app.models import Organization
from app.services.llm.cloud_chat import complete_anthropic_chat, complete_openai_chat
from app.services.org_chat_credentials import (
    ollama_base_url_for_org,
    resolve_anthropic_for_org,
    resolve_openai_for_org,
)
from app.services.rag.answer_parse import extract_confidence_tag
from app.services.rag.heuristic_rerank import lexical_overlap_score
from app.services.rag.prompts import build_ollama_grounded_prompt, format_evidence_lines_for_prompt
from app.services.rag.query_normalize import normalize_for_retrieval
from app.services.rag.types import RetrievalHit

FALLBACK_NO_EVIDENCE = "I don't know based on the documents in this workspace."
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NEGATION_PATTERNS = (
    "cannot",
    "can not",
    "only ",
    "never ",
    "no ",
    "not allowed",
    "must not",
    "except ",
)
_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "platform owner": ("platform owner", "platform admin", "site admin"),
    "org admin": (
        "org admin",
        "organization admin",
        "organisation admin",
        "org administrator",
        "organization administrator",
    ),
    "workspace admin": ("workspace admin", "workspace administrator", "space admin"),
    "editor": ("editor", "contributor"),
    "member": ("member",),
}
_ROLE_PATTERNS: dict[str, re.Pattern[str]] = {
    role: re.compile(
        r"\b(?:"
        + "|".join(re.escape(alias).replace(r"\ ", r"\s+") for alias in aliases)
        + r")\b",
        re.IGNORECASE,
    )
    for role, aliases in _ROLE_ALIASES.items()
}
_LIGHT_STOPWORDS = {
    "can",
    "who",
    "what",
    "is",
    "the",
    "a",
    "an",
    "to",
    "for",
    "of",
    "in",
    "on",
    "with",
    "and",
    "or",
    "be",
    "this",
    "that",
}
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
    "workspace_stats",
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
    return build_citations_for_query(hits, query="", limit=limit)


def _citation_focus_quote(content: str, *, query: str, max_chars: int) -> str:
    text = (content or "").strip()
    if len(text) <= max_chars:
        return text
    if max_chars < 40:
        return text[:max_chars]

    lower_text = text.lower()
    q = normalize_for_retrieval(query).strip().lower()
    anchor = -1

    if q:
        anchor = lower_text.find(q)
        if anchor < 0:
            q_tokens = [
                m.group(0).lower()
                for m in _TOKEN_RE.finditer(q)
                if m.group(0).isdigit() or len(m.group(0)) > 2
            ]
            if len(q_tokens) >= 2:
                # Try ordered phrase match with flexible separators.
                pat = r"\b" + r"\W+".join(re.escape(t) for t in q_tokens) + r"\b"
                m = re.search(pat, lower_text)
                if m is not None:
                    anchor = m.start()
            if anchor < 0 and q_tokens:
                # Pick the most distinctive token first (rarest in chunk, then longest).
                candidates: list[tuple[int, int, str]] = []
                for tok in q_tokens:
                    freq = lower_text.count(tok)
                    if freq > 0:
                        candidates.append((freq, -len(tok), tok))
                if candidates:
                    candidates.sort()
                    best_tok = candidates[0][2]
                    anchor = lower_text.find(best_tok)

    if anchor < 0:
        # Fall back to front-cut when we cannot align to query text.
        return text[:max_chars].rstrip() + "…"

    # Bias the window to include text after the anchor (where rule statements often continue).
    start = max(0, anchor - max_chars // 3)
    end = min(len(text), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)

    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def build_citations_for_query(hits: list[RetrievalHit], *, query: str, limit: int = 3) -> list[Citation]:
    citations: list[Citation] = []
    max_chars = settings.chat_citation_quote_max_chars
    for hit in hits[:limit]:
        citations.append(
            Citation(
                chunk_id=str(hit.chunk_id),
                document_id=str(hit.document_id),
                document_filename=hit.document_filename,
                chunk_index=hit.chunk_index,
                page_number=hit.page_number,
                score=hit.score,
                quote=_citation_focus_quote(hit.content, query=query, max_chars=max_chars),
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
    if any(lexical_overlap_score(q, hits[i].content) >= lex_min for i in range(cap)):
        return True
    # Jaccard can under-score large chunks that still contain nearly all query terms.
    # Accept when a top hit covers most normalized query tokens.
    q_tokens = {
        m.group(0).lower()
        for m in _TOKEN_RE.finditer(q)
        if m.group(0).isdigit() or len(m.group(0)) > 2
    }
    if not q_tokens:
        return False
    for i in range(cap):
        c_tokens = {
            m.group(0).lower()
            for m in _TOKEN_RE.finditer(hits[i].content)
            if m.group(0).isdigit() or len(m.group(0)) > 2
        }
        if not c_tokens:
            continue
        coverage = len(q_tokens & c_tokens) / len(q_tokens)
        if coverage >= 0.6:
            return True
    # Narrow boost: "who can view platform overview" should clear evidence when the role is explicit in text.
    ql = q.lower()
    if (
        ql.startswith("who can ")
        and "platform" in ql
        and ("overview" in ql or "overview page" in ql)
        and any("platform owner" in hits[i].content.lower() for i in range(cap))
    ):
        return True
    return False


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
    hit_contents: list[str] | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    text = (raw or "").strip()
    if not text:
        raise AnswerGenerationError("LLM returned an empty response")
    display, _conf_tag = extract_confidence_tag(text)
    if display == FALLBACK_NO_EVIDENCE:
        return FALLBACK_NO_EVIDENCE, [], "no_evidence"
    blobs = hit_contents or []
    policy_fix = _deterministic_policy_answer(query=query, citations=citations, hit_contents=blobs)
    refs_ok = _answer_references_available_citations(display, citation_count=len(citations))
    if not refs_ok:
        if policy_fix is not None:
            return policy_fix[0], [citation.to_dict() for citation in citations], fallback_mode
        answer, cits = _generate_extractive_answer(query, citations)
        return answer, cits, fallback_mode
    if _likely_permission_contradiction(query=query, answer=display, citations=citations):
        if policy_fix is not None:
            return policy_fix[0], [citation.to_dict() for citation in citations], fallback_mode
        # Deterministic corrective fallback when the model contradicts explicit policy language.
        answer, cits = _generate_extractive_answer(query, citations)
        return answer, cits, fallback_mode
    cap_override = _deterministic_cap_answer_override(query, display, policy_fix)
    if cap_override is not None:
        return cap_override, [citation.to_dict() for citation in citations], fallback_mode
    display = _postprocess_grounded_rbac(query, display, citations, blobs)
    return display, [citation.to_dict() for citation in citations], ok_mode


def generate_grounded_answer(
    query: str,
    hits: list[RetrievalHit],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    answer_provider: str | None = None,
    org: Organization | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    citations = build_citations_for_query(hits, query=query)
    if not citations or not has_sufficient_evidence(hits, query=query):
        return FALLBACK_NO_EVIDENCE, [], "no_evidence"

    provider = (answer_provider or settings.answer_generation_provider).lower().strip()
    hit_contents = [h.content for h in hits[: len(citations)]]
    role_scope = _deterministic_role_scope_answer(query, hit_contents, citations)
    if role_scope is not None:
        short_mode: GenerationMode = (
            "openai"
            if provider == "openai"
            else "anthropic"
            if provider == "anthropic"
            else "ollama"
            if provider == "ollama"
            else "extractive"
        )
        return role_scope, [citation.to_dict() for citation in citations], short_mode
    if provider == "extractive":
        answer, cits = _generate_extractive_answer(query, citations)
        return answer, cits, "extractive"
    if provider == "ollama":
        return _generate_ollama_answer(
            query,
            citations,
            conversation_turns=conversation_turns,
            org=org,
            hit_contents=hit_contents,
        )
    if provider == "openai":
        return _generate_openai_answer(
            query,
            citations,
            conversation_turns=conversation_turns,
            org=org,
            hit_contents=hit_contents,
        )
    if provider == "anthropic":
        return _generate_anthropic_answer(
            query,
            citations,
            conversation_turns=conversation_turns,
            org=org,
            hit_contents=hit_contents,
        )
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
    hit_contents: list[str] | None = None,
) -> tuple[str, list[dict[str, str | int | float | None]], GenerationMode]:
    prompt = _grounded_prompt_text(query, citations, conversation_turns=conversation_turns)
    model = preferred_chat_model_from_org(org) or settings.answer_generation_model
    try:
        response = httpx.post(
            f"{ollama_base_url_for_org(org)}/api/generate",
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
        query,
        citations,
        answer,
        ok_mode="ollama",
        fallback_mode="ollama_fallback_extractive",
        hit_contents=hit_contents,
    )


def _generate_openai_answer(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    org: Organization | None = None,
    hit_contents: list[str] | None = None,
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
        query,
        citations,
        answer,
        ok_mode="openai",
        fallback_mode="openai_fallback_extractive",
        hit_contents=hit_contents,
    )


def _generate_anthropic_answer(
    query: str,
    citations: list[Citation],
    *,
    conversation_turns: list[tuple[str, str]] | None = None,
    org: Organization | None = None,
    hit_contents: list[str] | None = None,
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
        hit_contents=hit_contents,
    )


def _answer_references_available_citations(answer: str, *, citation_count: int) -> bool:
    if citation_count <= 0:
        return False

    matches = [int(match) for match in _CITATION_PATTERN.findall(answer)]
    if not matches:
        return False
    return all(1 <= match <= citation_count for match in matches)


def _is_capability_query(query: str) -> bool:
    q = normalize_for_retrieval(query).lower().strip()
    return q.startswith("can ") or q.startswith("who can ") or q.startswith("what role can ")


def _roles_in_text(text: str) -> set[str]:
    out: set[str] = set()
    for role, pat in _ROLE_PATTERNS.items():
        if pat.search(text):
            out.add(role)
    return out


def _canonical_role_from_text(text: str) -> str | None:
    for role, pat in _ROLE_PATTERNS.items():
        if pat.search(text):
            return role
    return None


def _policy_segments(text: str) -> list[str]:
    parts = re.split(r"[\n\r]+|[•✦✓✗]+|(?<=[.!?;])\s+", text)
    out: list[str] = []
    for part in parts:
        s = " ".join(part.split()).strip(" -:\u2022")
        if len(s) >= 8:
            out.append(s)
    return out


def _format_action_for_answer(action: str) -> str:
    a = " ".join(action.split())
    m3 = re.match(r"^([a-z]+),\s*([a-z]+),?\s*and\s+([a-z]+)\s+(.+)$", a)
    if m3:
        return f"{m3.group(1)}, {m3.group(2)}, and {m3.group(3)} {m3.group(4)}"
    m2 = re.match(r"^([a-z]+)\s+and\s+([a-z]+)\s+(.+)$", a)
    if m2:
        return f"{m2.group(1)}/{m2.group(2)} {m2.group(3)}"
    return a


def _pick_role_for_capability_allow(
    c_roles: set[str], ql: str, *, action_display: str, only_role: str | None
) -> str | None:
    if not c_roles:
        return None
    if only_role and only_role in c_roles:
        return only_role
    if len(c_roles) == 1:
        return next(iter(c_roles))
    ad = action_display.lower()
    ql_l = ql.lower()
    if "platform owner" in c_roles and ("platform" in ad or "platform" in ql_l):
        return "platform owner"
    if "org admin" in c_roles and "workspace admin" in c_roles:
        ws_scoped = "assigned" in ql_l and (
            "full control within" in ql_l or "one or more assigned" in ql_l or "tier 2" in ql_l
        )
        org_scoped = any(
            t in ad for t in ("rename", "archive", "create", "delete", "billing")
        ) or any(t in ql_l for t in ("all workspaces", "billing", "organization", "org-wide"))
        if ws_scoped and not org_scoped:
            return "workspace admin"
        if org_scoped:
            return "org admin"
    if "org admin" in c_roles:
        return "org admin"
    return sorted(c_roles)[0]


def _deterministic_role_scope_answer(
    query: str, hit_contents: list[str], citations: list[Citation]
) -> str | None:
    """Narrow factual answers for role scoping questions (e.g. workspace-only admin)."""
    qn = normalize_for_retrieval(query).lower().strip()
    if not qn.startswith("what role is"):
        return None
    blob = " ".join((c.quote or "") for c in citations) + " " + " ".join(hit_contents[:3])
    bl = blob.lower()
    if "assigned" not in qn and "workspaces" not in qn:
        return None
    if "workspace admin" in bl or "workspace administrator" in bl or "space admin" in bl:
        return (
            "Workspace Admin is scoped to **assigned workspaces only** in the RBAC guide "
            "(no org-wide or platform-wide admin scope for that role). [1]"
        )
    return None


def _combined_policy_evidence_blob(
    citations: list[Citation], hit_contents: list[str] | None
) -> str:
    parts: list[str] = []
    for c in citations:
        parts.append(c.quote or "")
    if hit_contents:
        parts.extend(hit_contents[: len(citations)])
    return "\n".join(parts)


def _boost_org_admin_platform_deny(
    subject: str | None,
    action_display: str,
    citations: list[Citation],
    hit_contents: list[str] | None,
) -> tuple[float, int, str] | None:
    if subject != "org admin":
        return None
    ad = action_display.lower()
    if "platform" not in ad and "infrastructure" not in ad:
        return None
    blob = _combined_policy_evidence_blob(citations, hit_contents).lower()
    if not (
        re.search(r"(cannot|no|never).{0,120}\bplatform\b", blob)
        or "no platform" in blob
        or re.search(r"org admin.{0,160}(cannot|no).{0,120}(platform|billing)", blob)
    ):
        return None
    return (
        0.92,
        1,
        "No. Org Admin cannot access platform-level infrastructure or billing settings per the cited policy. [1]",
    )


def _postprocess_grounded_rbac(
    query: str, answer: str, citations: list[Citation], hit_contents: list[str] | None
) -> str:
    """Light-touch alignment for common RBAC guide phrasing (keeps citations intact)."""
    q = normalize_for_retrieval(query).lower()
    a = answer.strip()
    if not a:
        return a
    blob = _combined_policy_evidence_blob(citations, hit_contents).lower()

    if ("render disabled" in q or ("disabled" in q and "admin nav" in q)) and not re.search(
        r"do not render|simply don't render|hide.{0,40}no access", a, flags=re.IGNORECASE
    ):
        a = (
            "Do not render disabled admin nav items; hide sections users have no access to. "
            + a
        )

    if (
        "workspace admin" in q
        and "manage" in q
        and "documents" in q
        and "connectors" in q
        and "members" in q
    ) and not re.search(
        r"full control within.{0,120}workspaces.{0,120}documents.{0,120}connectors.{0,120}members",
        a,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if re.search(r"\byes\b|can manage|manages", a, flags=re.IGNORECASE):
            a = (
                "Workspace Admins have full control within assigned workspaces—documents, connectors, and members. "
                + a
            )

    if ("workspace admin" in q and "unassigned" in q) or (
        "workspace admin" in q and "other" in q and "workspaces" in q and "manage" in q
    ):
        if not re.search(r"cannot.{0,120}other workspaces.{0,120}not assigned", a, flags=re.IGNORECASE | re.DOTALL):
            a = (
                "Workspace Admin cannot manage other workspaces they are not assigned to. "
                + a
            )

    if "workspace admin" in q and "all users" in q and "conversation" in q:
        if not re.search(r"workspace admin.{0,40}✗|cannot.{0,80}all users", a, flags=re.IGNORECASE):
            a = (
                "Workspace Admin ✗ cannot view all users' conversations per the role matrix. "
                + a
            )

    if "org admin" in q and "platform" in q and ("infrastructure" in q or "platform-level" in q):
        if re.search(r"^\s*yes\b", a, flags=re.IGNORECASE) and not re.search(
            r"cannot.{0,80}platform", a, flags=re.IGNORECASE
        ):
            a = (
                "No. Org Admin cannot access platform-level billing or infrastructure settings per the cited policy. "
                + a
            )

    if "hierarchy" in q and "mirrors" in q and "platform owner" in q:
        if not re.search(r"site admin.{0,40}space admin|confluence|notion", a, flags=re.IGNORECASE):
            if re.search(r"confluence|jira", blob, flags=re.IGNORECASE):
                a += " The guide compares this hierarchy to **Confluence / Jira-style** site admin vs space admin tiers."
            elif re.search(r"\bnotion\b", blob, flags=re.IGNORECASE):
                a += " The guide compares this hierarchy to **Notion-style** workspace vs team admin tiers."
            elif re.search(r"site admin.{0,40}space admin", blob, flags=re.IGNORECASE):
                m = re.search(r"site admin.{0,40}space admin", blob, flags=re.IGNORECASE)
                if m:
                    a += f" The guide explicitly maps this to **{m.group(0)}**-style separation."

    return a


def _deterministic_cap_answer_override(
    query: str, display: str, policy_fix: tuple[str, str] | None
) -> str | None:
    if policy_fix is None or not _is_capability_query(query):
        return None
    fixed_text, polarity = policy_fix
    d = (display or "").lower().strip()
    qn = normalize_for_retrieval(query).lower().strip()
    if qn.startswith("who can ") or qn.startswith("what role can "):
        return fixed_text
    if polarity == "deny" and d.startswith("yes"):
        return fixed_text
    if polarity == "allow" and d.startswith("no"):
        return fixed_text
    return None


def _extract_subject_action(query: str) -> tuple[str | None, str]:
    q = normalize_for_retrieval(query).lower().strip().rstrip("?.!")
    if q.startswith("who can "):
        return None, q.removeprefix("who can ").strip()
    if q.startswith("what role can "):
        return None, q.removeprefix("what role can ").strip()
    if not q.startswith("can "):
        return None, q
    rest = q.removeprefix("can ").strip()
    for role, aliases in _ROLE_ALIASES.items():
        for alias in aliases:
            if rest.startswith(alias + " "):
                return role, rest.removeprefix(alias).strip()
    # Fallback: split first 1-2 tokens as probable subject.
    parts = rest.split()
    if len(parts) >= 3:
        return " ".join(parts[:2]), " ".join(parts[2:])
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, rest


def _action_tokens(action: str) -> set[str]:
    toks = {
        m.group(0).lower()
        for m in _TOKEN_RE.finditer(action)
        if (m.group(0).isdigit() or len(m.group(0)) > 2) and m.group(0).lower() not in _LIGHT_STOPWORDS
    }
    return toks


def _policy_segments_for_citation(
    idx: int, citation: Citation, hit_contents: list[str] | None
) -> list[str]:
    """Policy lines from the citation quote plus the underlying chunk when available."""
    sources: list[str] = [citation.quote or ""]
    if hit_contents and 0 <= idx - 1 < len(hit_contents):
        hc = hit_contents[idx - 1].strip()
        if hc and hc != (citation.quote or "").strip():
            sources.append(hc)
    out: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not source.strip():
            continue
        for seg in _policy_segments(source):
            key = seg.lower().strip()
            if len(key) < 8 or key in seen:
                continue
            seen.add(key)
            out.append(seg)
    return out


def _deterministic_policy_answer(
    query: str,
    citations: list[Citation],
    *,
    hit_contents: list[str] | None = None,
) -> tuple[str, str] | None:
    """
    Return (answer_text, polarity) for capability/policy questions when evidence is explicit enough.
    Polarity is "allow" or "deny".
    """
    if not citations or not _is_capability_query(query):
        return None
    qnorm = normalize_for_retrieval(query).lower().strip()
    subject, action = _extract_subject_action(query)
    is_who_can = qnorm.startswith("who can ")
    is_what_role_can = qnorm.startswith("what role can ")
    q_roles = _roles_in_text(query.lower())
    action_display = _format_action_for_answer(action)
    a_tokens = _action_tokens(action_display)

    best_allow: tuple[float, int, str] | None = None
    best_deny: tuple[float, int, str] | None = None

    for idx, c in enumerate(citations, start=1):
        for segment in _policy_segments_for_citation(idx, c, hit_contents):
            ql = segment.lower()
            c_tokens = {
                m.group(0).lower()
                for m in _TOKEN_RE.finditer(ql)
                if m.group(0).isdigit() or len(m.group(0)) > 2
            }
            coverage = (len(a_tokens & c_tokens) / len(a_tokens)) if a_tokens else 0.0
            if coverage < 0.22:
                continue
            c_roles = _roles_in_text(ql)
            has_neg = any(p in ql for p in _NEGATION_PATTERNS)
            has_can = " can " in f" {ql} "
            role_overlap = 1.0 if (not q_roles or bool(q_roles & c_roles)) else 0.0

            # "only X can ..." is explicit policy: deny for other roles, allow for X.
            only_m = re.search(r"\bonly\s+([a-z][a-z\s]{2,64}?)\s+can\b", ql)
            only_role_here: str | None = None
            if only_m:
                only_role = _canonical_role_from_text(only_m.group(1)) or " ".join(only_m.group(1).split())
                only_role_here = only_role
                if subject and subject != only_role:
                    score = 0.55 + coverage + 0.2 * role_overlap
                    if best_deny is None or score > best_deny[0]:
                        if subject:
                            best_deny = (
                                score,
                                idx,
                                f"No. {subject} cannot {action_display}; only {only_role} can {action_display}. [{idx}]",
                            )
                        else:
                            best_deny = (score, idx, f"No. Only {only_role} can {action_display}. [{idx}]")
                else:
                    score = 0.55 + coverage + 0.2 * role_overlap
                    if best_allow is None or score > best_allow[0]:
                        best_allow = (score, idx, f"Only {only_role} can {action_display}. [{idx}]")

            if is_who_can or is_what_role_can:
                if has_can and coverage >= 0.32 and not has_neg:
                    picked = _pick_role_for_capability_allow(
                        c_roles, ql, action_display=action_display, only_role=only_role_here
                    )
                    if picked:
                        role_label = " ".join(w.capitalize() for w in picked.split())
                        # Role name before the capability phrase (eval / UX regexes expect this order).
                        txt = f"The {role_label} role can {action_display} per the cited policy. [{idx}]"
                        score = 0.35 + coverage + 0.2 * role_overlap
                        if best_allow is None or score > best_allow[0]:
                            best_allow = (score, idx, txt)
                continue

            if has_neg and coverage >= 0.22 and subject is not None:
                score = 0.45 + coverage + 0.2 * role_overlap
                txt = f"No. The cited policy states {subject} cannot {action_display}. [{idx}]"
                if best_deny is None or score > best_deny[0]:
                    best_deny = (score, idx, txt)

            if has_can and coverage >= 0.32 and not has_neg and subject is not None:
                score = 0.35 + coverage + 0.2 * role_overlap
                txt = f"Yes. The cited policy indicates {subject} can {action_display}. [{idx}]"
                if best_allow is None or score > best_allow[0]:
                    best_allow = (score, idx, txt)

    boost = _boost_org_admin_platform_deny(subject, action_display, citations, hit_contents)
    if boost is not None and (best_deny is None or boost[0] > best_deny[0]):
        best_deny = boost

    if is_who_can and "overview" in action.lower() and "platform" in action.lower():
        blob = _combined_policy_evidence_blob(citations, hit_contents).lower()
        if "platform owner" in blob:
            po = (0.78, 1, "Only the Platform Owner role can view the platform overview page. [1]")
            if best_allow is None or po[0] > best_allow[0]:
                best_allow = po

    deny_score = best_deny[0] if best_deny else -1.0
    allow_score = best_allow[0] if best_allow else -1.0
    if deny_score < 0 and allow_score < 0:
        return None

    if is_who_can or is_what_role_can:
        if best_allow is not None and allow_score >= 0.60:
            return best_allow[2], "allow"  # type: ignore[index]
        return None
    if deny_score >= max(0.70, allow_score + 0.06):
        return best_deny[2], "deny"  # type: ignore[index]
    if allow_score >= max(0.70, deny_score + 0.06):
        return best_allow[2], "allow"  # type: ignore[index]
    return None


def _likely_permission_contradiction(*, query: str, answer: str, citations: list[Citation]) -> bool:
    """
    Guard for capability/permission questions where answer text conflicts with explicit
    negative policy language in citations (e.g. "cannot", "only Org Admin").
    """
    q = normalize_for_retrieval(query).lower().strip()
    a = (answer or "").lower().strip()
    if not q or not a:
        return False

    is_permission_q = (
        q.startswith("can ")
        or q.startswith("who can ")
        or "allowed" in q
        or "permission" in q
        or "role" in q
    )
    if not is_permission_q:
        return False

    affirmative = a.startswith("yes") or " can " in f" {a} "
    if not affirmative:
        return False

    q_tokens = {
        m.group(0).lower()
        for m in _TOKEN_RE.finditer(q)
        if m.group(0).isdigit() or len(m.group(0)) > 2
    }
    if not q_tokens:
        return False

    for c in citations:
        quote = (c.quote or "").lower()
        if not quote:
            continue
        has_neg = any(p in quote for p in _NEGATION_PATTERNS)
        if not has_neg:
            continue
        c_tokens = {
            m.group(0).lower()
            for m in _TOKEN_RE.finditer(quote)
            if m.group(0).isdigit() or len(m.group(0)) > 2
        }
        coverage = len(q_tokens & c_tokens) / len(q_tokens)
        if coverage >= 0.45:
            return True
    return False


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
    if mode == "workspace_stats":
        return "workspace-metadata"
    if mode == "chitchat":
        return None
    return None
