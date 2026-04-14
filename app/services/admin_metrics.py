"""Admin aggregates/lists for dashboard, docs, connectors, and audit views."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Document, DocumentChunk, DocumentStatus, IntegrationConnector, QueryLog, User, Workspace
from app.services.chat import FALLBACK_NO_EVIDENCE

_CONF_SCORE = case(
    (QueryLog.confidence == "high", 0.85),
    (QueryLog.confidence == "medium", 0.55),
    (QueryLog.confidence == "low", 0.35),
    else_=0.5,
)


def _month_start_utc(now: datetime | None = None) -> datetime:
    n = now or datetime.now(timezone.utc)
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def build_admin_metrics_summary(db: Session, *, organization_id: UUID | None) -> dict[str, Any]:
    """Return JSON shape expected by `AdminDashboardPage` and stakeholder explainer (usage + gaps)."""
    now = datetime.now(timezone.utc)
    month_start = _month_start_utc(now)
    day_start_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)
    day_labels = [now.date() - timedelta(days=i) for i in range(29, -1, -1)]

    def ql_filter(q):
        if organization_id is not None:
            return q.filter(QueryLog.organization_id == organization_id)
        return q

    queries_this_month = (
        ql_filter(db.query(QueryLog))
        .filter(QueryLog.created_at >= month_start)
        .with_entities(func.count(QueryLog.id))
        .scalar()
        or 0
    )

    active_users_7d = (
        ql_filter(db.query(QueryLog))
        .filter(QueryLog.created_at >= day_start_7d, QueryLog.user_id.isnot(None))
        .with_entities(func.count(func.distinct(QueryLog.user_id)))
        .scalar()
        or 0
    )

    avg_ms = ql_filter(db.query(QueryLog).filter(QueryLog.duration_ms.isnot(None))).with_entities(
        func.avg(QueryLog.duration_ms)
    ).scalar()
    avg_response_time_ms = int(round(float(avg_ms))) if avg_ms is not None else 0

    doc_q = db.query(Document).filter(Document.status == DocumentStatus.indexed.value)
    if organization_id is not None:
        doc_q = doc_q.filter(Document.organization_id == organization_id)
    documents_indexed = doc_q.with_entities(func.count(Document.id)).scalar() or 0

    day_trunc = func.date_trunc("day", QueryLog.created_at)
    dq = (
        db.query(day_trunc.label("d"), func.count(QueryLog.id))
        .select_from(QueryLog)
        .filter(QueryLog.created_at >= since_30d)
    )
    if organization_id is not None:
        dq = dq.filter(QueryLog.organization_id == organization_id)
    day_rows = dq.group_by(day_trunc).all()
    day_counts: dict[str, int] = {}
    for d, c in day_rows:
        if d is None:
            continue
        ds = d.date() if hasattr(d, "date") else d
        day_counts[str(ds)] = int(c)

    queries_per_day = [{"date": str(d), "count": int(day_counts.get(str(d), 0))} for d in day_labels]

    top_stmt = (
        select(
            QueryLog.question,
            func.count(QueryLog.id).label("frequency"),
            func.max(QueryLog.created_at).label("last_asked"),
            func.avg(_CONF_SCORE).label("avg_confidence"),
        )
        .group_by(QueryLog.question)
        .order_by(func.count(QueryLog.id).desc())
        .limit(15)
    )
    if organization_id is not None:
        top_stmt = top_stmt.where(QueryLog.organization_id == organization_id)
    top_rows = db.execute(top_stmt).all()
    top_queries = [
        {
            "text": (r.question or "")[:500],
            "frequency": int(r.frequency),
            "avg_confidence": float(r.avg_confidence or 0.0),
            "last_asked": (r.last_asked.date().isoformat() if r.last_asked else now.date().isoformat()),
        }
        for r in top_rows
    ]

    gap_cond = or_(
        _CONF_SCORE < 0.4,
        func.coalesce(QueryLog.answer, "").contains(FALLBACK_NO_EVIDENCE),
    )
    u_stmt = select(QueryLog).where(gap_cond).order_by(QueryLog.created_at.desc()).limit(25)
    if organization_id is not None:
        u_stmt = u_stmt.where(QueryLog.organization_id == organization_id)
    u_rows = db.scalars(u_stmt).all()
    unanswered_queries = []
    for row in u_rows:
        conf_map = {"high": 0.85, "medium": 0.55, "low": 0.35}.get((row.confidence or "").lower(), 0.45)
        if row.answer and FALLBACK_NO_EVIDENCE in row.answer:
            conf_map = min(conf_map, 0.25)
        unanswered_queries.append(
            {
                "text": (row.question or "")[:500],
                "confidence": float(conf_map),
                "last_asked": row.created_at.date().isoformat() if row.created_at else now.date().isoformat(),
            }
        )

    return {
        "totals": {
            "queries_this_month": int(queries_this_month),
            "active_users_7d": int(active_users_7d),
            "documents_indexed": int(documents_indexed),
            "avg_response_time_ms": int(avg_response_time_ms),
        },
        "queries_per_day": queries_per_day,
        "top_queries": top_queries if top_queries else [],
        "unanswered_queries": unanswered_queries,
    }


def list_connectors_for_org(db: Session, organization_id: UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(IntegrationConnector)
        .filter(IntegrationConnector.organization_id == organization_id)
        .order_by(IntegrationConnector.connector_type.asc())
        .all()
    )
    out = []
    for r in rows:
        nid = r.nango_connection_id or ""
        out.append(
            {
                "id": str(r.id),
                "connector_type": r.connector_type,
                "status": r.status,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
                "document_count": r.document_count,
                "nango_connection_id": nid[:12] + "…" if len(nid) > 12 else nid,
            }
        )
    return out


def list_documents_for_org(
    db: Session,
    *,
    organization_id: UUID,
    workspace_id: UUID | None = None,
    q: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    chunk_count_subq = (
        db.query(DocumentChunk.document_id.label("doc_id"), func.count(DocumentChunk.id).label("chunk_count"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    qry = (
        db.query(Document, Workspace.name.label("workspace_name"), chunk_count_subq.c.chunk_count)
        .join(Workspace, Workspace.id == Document.workspace_id)
        .outerjoin(chunk_count_subq, chunk_count_subq.c.doc_id == Document.id)
        .filter(Document.organization_id == organization_id)
        .order_by(Document.updated_at.desc())
        .limit(max(1, min(limit, 1000)))
    )
    if workspace_id is not None:
        qry = qry.filter(Document.workspace_id == workspace_id)
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(
            or_(
                Document.filename.ilike(like),
                func.coalesce(Document.source_type, "").ilike(like),
            )
        )
    out: list[dict[str, Any]] = []
    for doc, ws_name, chunk_count in qry.all():
        out.append(
            {
                "id": str(doc.id),
                "workspace_id": str(doc.workspace_id),
                "workspace_name": ws_name,
                "filename": doc.filename,
                "source_type": doc.source_type,
                "status": doc.status,
                "page_count": doc.page_count or 0,
                "chunk_count": int(chunk_count or 0),
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                "last_indexed_at": doc.last_indexed_at.isoformat() if doc.last_indexed_at else None,
            }
        )
    return out


def list_audit_events_for_org(
    db: Session,
    *,
    organization_id: UUID,
    action: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    qry = (
        db.query(AuditLog, User.email.label("actor_email"))
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .filter(AuditLog.organization_id == organization_id)
    )
    if action:
        qry = qry.filter(AuditLog.action == action.strip())
    rows = qry.order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 1000))).all()
    out: list[dict[str, Any]] = []
    for ev, actor_email in rows:
        out.append(
            {
                "id": str(ev.id),
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
                "actor_email": actor_email or "system",
                "action": ev.action,
                "target_type": ev.target_type,
                "target_id": str(ev.target_id) if ev.target_id else None,
                "workspace_id": str(ev.workspace_id) if ev.workspace_id else None,
                "metadata": ev.metadata_json or {},
            }
        )
    return out
