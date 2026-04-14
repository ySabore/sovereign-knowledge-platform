"""Prompt assembly for the grounded chat path (no network I/O)."""

from __future__ import annotations

from app.services.rag.answer_parse import estimate_tokens

# Layer 3.2-style: keep history small so Evidence stays the authority.
CHAT_HISTORY_MAX_TURNS = 3
CHAT_HISTORY_MAX_TOKEN_BUDGET = 4000
CHAT_TURN_CHAR_CAP = 2000


def format_evidence_lines_for_prompt(
    citations_payload: list[tuple[str, str | None, str]],
) -> list[str]:
    """
    Build numbered evidence lines for the LLM prompt.

    Each tuple is (document_filename, page_label_or_none, quote_text).
    Numbers [1]..[n] map to citation indices (same as [DOC_n] in the spec).
    """
    lines: list[str] = []
    for idx, (filename, page, quote) in enumerate(citations_payload, start=1):
        page_part = f", page {page}" if page is not None else ""
        lines.append(f"[{idx}] {filename}{page_part}: {quote}")
    return lines


def _join_turn_lines(turns: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for user_msg, assistant_msg in turns:
        parts.append(f"User: {user_msg}")
        parts.append(f"Assistant: {assistant_msg}")
    return "\n".join(parts)


def trim_conversation_turns_for_prompt(
    turns: list[tuple[str, str]],
    *,
    max_turns: int = CHAT_HISTORY_MAX_TURNS,
    max_token_budget: int = CHAT_HISTORY_MAX_TOKEN_BUDGET,
) -> list[tuple[str, str]]:
    """Keep up to `max_turns` recent turns; drop oldest until under token budget (then per-message cap)."""
    if not turns:
        return []
    capped = [(u[:CHAT_TURN_CHAR_CAP], a[:CHAT_TURN_CHAR_CAP]) for u, a in turns[-max_turns:]]
    trimmed = list(capped)
    while len(trimmed) > 1 and estimate_tokens(_join_turn_lines(trimmed)) > max_token_budget:
        trimmed.pop(0)
    body = _join_turn_lines(trimmed)
    while estimate_tokens(body) > max_token_budget and trimmed:
        u, a = trimmed[0]
        if len(u) > 80:
            trimmed[0] = (u[: max(len(u) // 2, 80)], a)
        elif len(a) > 80:
            trimmed[0] = (u, a[: max(len(a) // 2, 80)])
        else:
            trimmed.pop(0)
        body = _join_turn_lines(trimmed)
    return trimmed


def build_ollama_grounded_prompt(
    *,
    query: str,
    evidence_lines: list[str],
    fallback_exact: str,
    conversation_turns: list[tuple[str, str]] | None = None,
) -> str:
    """Assemble the constrained RAG prompt sent to the generative model."""
    evidence_block = "\n".join(evidence_lines)
    rules = (
        "You are a precise knowledge assistant. Answer using ONLY the Evidence block below.\n"
        "Rules:\n"
        f"1. If the Evidence is insufficient, reply exactly: {fallback_exact}\n"
        "2. Every factual claim must cite Evidence using inline markers [1], [2], … matching the Evidence numbers.\n"
        "3. Do not invent facts or use general knowledge beyond what Evidence supports.\n"
        "4. Be concise: a few sentences for simple questions; more only when Evidence requires it.\n"
        "5. When a source line includes a page number, you may write e.g. [1] or refer to page in the sentence.\n"
        "6. On the last line after your answer, output exactly one line: "
        "<confidence>high</confidence>, <confidence>medium</confidence>, or <confidence>low</confidence> "
        "based on how directly Evidence answers the question.\n"
    )
    history_block = ""
    if conversation_turns:
        kept = trim_conversation_turns_for_prompt(conversation_turns)
        if kept:
            history_block = (
                "Recent conversation (context only; prefer Evidence over prior assistant replies):\n"
                f"{_join_turn_lines(kept)}\n\n"
            )
    return (
        f"{rules}\n"
        f"{history_block}"
        f"Question: {query}\n\n"
        "Evidence:\n"
        f"{evidence_block}\n\n"
        "Respond with a concise answer, inline citations [n] as above, then the confidence line."
    )
