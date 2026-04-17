from __future__ import annotations

from datetime import timedelta
import re
from typing import Literal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ChatSession, Document, DocumentChunk, DocumentStatus, utcnow

WorkspaceFactMode = Literal["workspace_stats"]


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip().lower())


def _has_any(query: str, terms: tuple[str, ...]) -> bool:
    return any(t in query for t in terms)


def is_workspace_fact_query(query: str) -> bool:
    q = _normalize_query(query)
    asks_count = _has_any(q, ("how many", "number of", "count of", "count"))
    about_docs = _has_any(q, ("document", "documents", "doc", "docs", "file", "files"))
    about_chunks = "chunk" in q
    asks_listing = _has_any(q, ("what documents", "which documents", "list documents", "show documents"))
    asks_chat_count = asks_count and _has_any(q, ("chat", "chats", "conversation", "conversations"))
    asks_time_window = _has_any(q, ("this week", "this month", "today", "last 7", "last seven", "last 30"))
    asks_source_mix = _has_any(q, ("source", "connector", "upload", "uploaded vs", "breakdown"))
    asks_newest = _has_any(q, ("newest", "latest", "recent files"))
    asks_failed_listing = _has_any(q, ("which failed", "failed documents", "failed files"))
    asks_stuck = _has_any(q, ("stuck", "stalled"))
    return (
        (asks_count and (about_docs or about_chunks))
        or asks_listing
        or asks_chat_count
        or (about_docs and asks_time_window)
        or (about_docs and asks_source_mix)
        or (about_docs and asks_newest)
        or asks_failed_listing
        or (about_docs and asks_stuck)
    )


def _document_counts(db: Session, workspace_id: UUID) -> dict[str, int]:
    rows = (
        db.query(Document.status, func.count(Document.id))
        .filter(Document.workspace_id == workspace_id)
        .group_by(Document.status)
        .all()
    )
    counts: dict[str, int] = {str(status): int(count) for status, count in rows}
    total = int(sum(counts.values()))
    counts["total"] = total
    counts.setdefault(DocumentStatus.indexed.value, 0)
    counts.setdefault(DocumentStatus.processing.value, 0)
    counts.setdefault(DocumentStatus.failed.value, 0)
    counts.setdefault(DocumentStatus.uploaded.value, 0)
    return counts


def _chunk_count(db: Session, workspace_id: UUID) -> int:
    return int(
        db.query(func.count(DocumentChunk.id))
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(Document.workspace_id == workspace_id)
        .scalar()
        or 0
    )


def _document_count_since(db: Session, workspace_id: UUID, *, days: int) -> int:
    since = utcnow() - timedelta(days=days)
    return int(
        db.query(func.count(Document.id))
        .filter(Document.workspace_id == workspace_id, Document.created_at >= since)
        .scalar()
        or 0
    )


def _chat_count_for_user(db: Session, workspace_id: UUID, *, user_id: UUID) -> int:
    return int(
        db.query(func.count(ChatSession.id))
        .filter(ChatSession.workspace_id == workspace_id, ChatSession.user_id == user_id)
        .scalar()
        or 0
    )


def _source_breakdown(db: Session, workspace_id: UUID) -> dict[str, int]:
    rows = (
        db.query(Document.source_type, func.count(Document.id))
        .filter(Document.workspace_id == workspace_id)
        .group_by(Document.source_type)
        .all()
    )
    breakdown: dict[str, int] = {str(source or "unknown"): int(count) for source, count in rows}
    return breakdown


def _list_document_names(
    db: Session,
    workspace_id: UUID,
    *,
    status: str | None = None,
    limit: int = 10,
) -> list[str]:
    query = db.query(Document.filename).filter(Document.workspace_id == workspace_id)
    if status:
        query = query.filter(Document.status == status)
    rows = query.order_by(Document.created_at.desc()).limit(limit).all()
    return [str(r[0]) for r in rows if r and r[0]]


def _processing_stuck_count(db: Session, workspace_id: UUID, *, minutes: int = 30) -> int:
    threshold = utcnow() - timedelta(minutes=minutes)
    return int(
        db.query(func.count(Document.id))
        .filter(
            Document.workspace_id == workspace_id,
            Document.status == DocumentStatus.processing.value,
            Document.updated_at < threshold,
        )
        .scalar()
        or 0
    )


def _format_source_breakdown(breakdown: dict[str, int]) -> str:
    if not breakdown:
        return "no sources yet"
    uploads = int(sum(count for src, count in breakdown.items() if "upload" in src))
    connectors = int(sum(count for src, count in breakdown.items() if "upload" not in src))
    parts = [f"{uploads} uploads", f"{connectors} connector-synced"]
    raw = ", ".join(f"{src}: {count}" for src, count in sorted(breakdown.items(), key=lambda x: (-x[1], x[0]))[:5])
    return f"{', '.join(parts)} (top sources: {raw})"


def answer_workspace_fact_query(
    db: Session,
    session: ChatSession,
    user_id: UUID,
    query: str,
) -> tuple[str, list[dict], WorkspaceFactMode] | None:
    q = _normalize_query(query)
    if not is_workspace_fact_query(q):
        return None

    counts = _document_counts(db, session.workspace_id)
    total = counts["total"]
    indexed = counts[DocumentStatus.indexed.value]
    processing = counts[DocumentStatus.processing.value]
    failed = counts[DocumentStatus.failed.value]
    uploaded = counts[DocumentStatus.uploaded.value]

    asks_docs = _has_any(q, ("document", "documents", "doc", "docs", "file", "files"))
    asks_chunks = "chunk" in q
    asks_indexed = "indexed" in q
    asks_processing = _has_any(q, ("processing", "in progress"))
    asks_failed = _has_any(q, ("failed", "error"))
    asks_uploaded = _has_any(q, ("uploaded", "not indexed"))
    asks_listing = _has_any(q, ("what documents", "which documents", "list documents", "show documents"))
    asks_time_week = _has_any(q, ("this week", "last 7", "last seven"))
    asks_time_month = _has_any(q, ("this month", "last 30"))
    asks_time_today = "today" in q
    asks_source_mix = _has_any(q, ("source", "connector", "upload", "uploaded vs", "breakdown"))
    asks_newest = _has_any(q, ("newest", "latest", "recent files"))
    asks_stuck = _has_any(q, ("stuck", "stalled"))
    asks_chat_count = _has_any(q, ("chat", "chats", "conversation", "conversations")) and _has_any(
        q, ("how many", "number of", "count")
    )
    asks_failed_listing = _has_any(q, ("which failed", "failed documents", "failed files"))

    if asks_chat_count:
        count = _chat_count_for_user(db, session.workspace_id, user_id=user_id)
        return (f"You currently have {count} conversations in this workspace.", [], "workspace_stats")

    if asks_time_today and asks_docs:
        count = _document_count_since(db, session.workspace_id, days=1)
        return (f"{count} documents were added in this workspace in the last 24 hours.", [], "workspace_stats")
    if asks_time_week and asks_docs:
        count = _document_count_since(db, session.workspace_id, days=7)
        return (f"{count} documents were added in this workspace in the last 7 days.", [], "workspace_stats")
    if asks_time_month and asks_docs:
        count = _document_count_since(db, session.workspace_id, days=30)
        return (f"{count} documents were added in this workspace in the last 30 days.", [], "workspace_stats")

    if asks_source_mix and asks_docs:
        breakdown = _source_breakdown(db, session.workspace_id)
        return (f"Source breakdown for this workspace: {_format_source_breakdown(breakdown)}.", [], "workspace_stats")

    if asks_failed_listing:
        names = _list_document_names(db, session.workspace_id, status=DocumentStatus.failed.value, limit=10)
        if not names:
            return ("No failed documents currently in this workspace.", [], "workspace_stats")
        return (f"Failed documents: {', '.join(names)}.", [], "workspace_stats")

    if asks_newest and asks_docs:
        names = _list_document_names(db, session.workspace_id, limit=10)
        if not names:
            return ("There are no documents in this workspace yet.", [], "workspace_stats")
        return (f"Newest documents in this workspace: {', '.join(names)}.", [], "workspace_stats")

    if asks_stuck and asks_docs:
        stuck = _processing_stuck_count(db, session.workspace_id, minutes=30)
        return (
            f"{stuck} processing documents look stalled (no update for over 30 minutes) in this workspace.",
            [],
            "workspace_stats",
        )

    if asks_listing:
        names = _list_document_names(db, session.workspace_id, limit=10)
        if not names:
            return ("There are no documents in this workspace yet.", [], "workspace_stats")
        extra = max(0, total - len(names))
        listed = ", ".join(names)
        suffix = f" and {extra} more" if extra > 0 else ""
        return (f"This workspace has {total} documents. Recent files: {listed}{suffix}.", [], "workspace_stats")

    if asks_chunks and _has_any(q, ("how many", "number of", "count")):
        chunks = _chunk_count(db, session.workspace_id)
        return (
            f"This workspace currently has {chunks} indexed chunks across {total} documents.",
            [],
            "workspace_stats",
        )

    if asks_docs and asks_indexed:
        return (f"This workspace has {indexed} indexed documents.", [], "workspace_stats")
    if asks_docs and asks_processing:
        return (f"This workspace has {processing} documents currently processing.", [], "workspace_stats")
    if asks_docs and asks_failed:
        return (f"This workspace has {failed} failed documents.", [], "workspace_stats")
    if asks_docs and asks_uploaded:
        return (f"This workspace has {uploaded} uploaded (not yet indexed) documents.", [], "workspace_stats")

    if asks_docs and _has_any(q, ("how many", "number of", "count")):
        return (
            "This workspace has "
            f"{total} documents total ({indexed} indexed, {processing} processing, {failed} failed, {uploaded} uploaded).",
            [],
            "workspace_stats",
        )

    return None

