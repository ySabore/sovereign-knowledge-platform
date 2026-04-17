"""Helpers for deriving readable chat session titles."""

from __future__ import annotations

LOW_SIGNAL_TITLES = {
    "chat",
    "conversation",
    "new conversation",
    "question",
    "questions",
    "help",
    "hi",
    "hello",
    "hey",
    "yo",
    "test",
    "testing",
    "thanks",
    "thank you",
}


def _normalize(text: str | None) -> str:
    return " ".join((text or "").strip().split()).lower()


def is_low_signal_chat_title(title: str | None) -> bool:
    normalized = _normalize(title)
    if not normalized:
        return True
    if normalized in LOW_SIGNAL_TITLES:
        return True
    if normalized.endswith("?"):
        normalized = normalized[:-1].strip()
    return normalized in LOW_SIGNAL_TITLES


def derive_chat_session_title(query: str, *, max_len: int = 120) -> str | None:
    """Generate a compact title from the first user prompt."""
    normalized = " ".join((query or "").strip().split())
    if not normalized:
        return None
    if len(normalized) <= max_len:
        return normalized
    clipped = normalized[:max_len].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip() or clipped
    return f"{clipped}…"


def should_replace_chat_title(current_title: str | None, query: str, *, user_turn_count: int) -> bool:
    """Allow one retitle on the second user turn when first title is generic."""
    if not current_title:
        return True
    if user_turn_count != 2:
        return False
    if not is_low_signal_chat_title(current_title):
        return False
    next_title = derive_chat_session_title(query)
    return bool(next_title and not is_low_signal_chat_title(next_title))

