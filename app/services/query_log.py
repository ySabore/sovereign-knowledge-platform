"""Persist chat/RAG turns to `query_logs` (Layer 5 Query model)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import QueryLog


def record_query_log(
    db: Session,
    *,
    organization_id: UUID,
    workspace_id: UUID,
    user_id: UUID | None,
    question: str,
    answer: str | None,
    citations: list[dict[str, Any]] | list[Any] | None,
    confidence: str | None,
    duration_ms: int | None = None,
) -> None:
    row = QueryLog(
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        question=question,
        answer=answer,
        citations_json=citations or [],
        confidence=confidence,
        duration_ms=duration_ms,
    )
    db.add(row)
