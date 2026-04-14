"""Load prior turns from `chat_messages` for multi-turn RAG prompts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatMessageRole
from app.services.rag.prompts import CHAT_HISTORY_MAX_TURNS


def load_recent_conversation_turns(
    db: Session,
    session_id: UUID,
    *,
    max_turns: int = CHAT_HISTORY_MAX_TURNS,
) -> list[tuple[str, str]]:
    """Ordered user/assistant pairs before the message being added for this turn."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    pairs: list[tuple[str, str]] = []
    i = 0
    while i + 1 < len(rows):
        if rows[i].role == ChatMessageRole.user.value and rows[i + 1].role == ChatMessageRole.assistant.value:
            pairs.append((rows[i].content, rows[i + 1].content))
            i += 2
        else:
            i += 1
    return pairs[-max_turns:] if pairs else []
