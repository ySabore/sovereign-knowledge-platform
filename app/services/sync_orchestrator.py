"""
Background sync orchestration (Component 3.4) — Nango fetch + `ingest_document`.

Use a worker or cron calling `run_connector_sync(connector_uuid)` instead of Inngest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import IntegrationConnector, Organization, Workspace, utcnow
from app.services.ingestion_service import IngestDocumentParams, ingest_document
from app.services.nango_client import DocumentFetchResult, fetch_documents, nango_configured

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConnectorSyncRequest:
    connector_id: str
    organization_id: UUID
    full_sync: bool = False


def _resolve_workspace_id(db: Session, org_id: UUID, cfg: dict[str, Any] | None) -> UUID | None:
    if cfg and cfg.get("workspace_id"):
        try:
            return UUID(str(cfg["workspace_id"]))
        except ValueError:
            pass
    ws = db.query(Workspace).filter(Workspace.organization_id == org_id).order_by(Workspace.created_at.asc()).first()
    return ws.id if ws else None


def _ingest_fetch_result(
    db: Session,
    doc: DocumentFetchResult,
    *,
    organization_id: UUID,
    workspace_id: UUID,
    connector_id: UUID,
    source_type: str,
) -> None:
    meta = dict(doc.metadata or {})
    if doc.last_modified:
        meta["lastModified"] = doc.last_modified.isoformat()
    ingest_document(
        db,
        IngestDocumentParams(
            content=doc.content,
            name=doc.name,
            source_type=source_type,
            external_id=doc.external_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            created_by=None,
            metadata=meta,
            permission_user_ids=None,
            source_url=doc.url,
            integration_connector_id=connector_id,
        ),
    )


def run_connector_sync(
    db: Session,
    connector_row_id: UUID,
    *,
    full_sync: bool = False,
    start_cursor: str | None = None,
) -> dict[str, Any]:
    conn = db.get(IntegrationConnector, connector_row_id)
    if conn is None:
        return {"status": "error", "detail": "connector not found"}

    org = db.get(Organization, conn.organization_id)
    if org is None:
        return {"status": "error", "detail": "organization not found"}

    cfg = conn.config if isinstance(conn.config, dict) else {}
    workspace_id = _resolve_workspace_id(db, org.id, cfg)
    if workspace_id is None:
        return {"status": "error", "detail": "No workspace; set config.workspace_id or create a workspace"}

    if not nango_configured():
        return {"status": "skipped", "detail": "NANGO_SECRET_KEY not configured"}

    conn.status = "syncing"
    db.commit()

    processed = 0
    errors: list[str] = []
    cursor: str | None = start_cursor

    try:
        while True:
            batch, cursor = fetch_documents(
                conn.connector_type,
                conn.nango_connection_id,
                cursor=cursor,
                connector_config=cfg,
            )
            for doc in batch:
                try:
                    _ingest_fetch_result(
                        db,
                        doc,
                        organization_id=org.id,
                        workspace_id=workspace_id,
                        connector_id=conn.id,
                        source_type=conn.connector_type,
                    )
                    processed += 1
                except Exception as exc:
                    logger.exception("ingest failed for %s", doc.external_id)
                    errors.append(f"{doc.external_id}: {exc}")
            if not cursor or not full_sync:
                break
    finally:
        conn = db.get(IntegrationConnector, connector_row_id)
        if conn:
            conn.last_synced_at = utcnow()
            conn.status = "active"
            conn.document_count = processed
            db.commit()

    return {
        "status": "ok",
        "connector_id": str(connector_row_id),
        "documents_ingested": processed,
        "errors": errors[:50],
    }


def enqueue_connector_sync(request: ConnectorSyncRequest) -> dict[str, Any]:
    logger.info(
        "enqueue_connector_sync stub: connector_id=%s org=%s full_sync=%s",
        request.connector_id,
        request.organization_id,
        request.full_sync,
    )
    return {
        "status": "accepted",
        "detail": "POST /connectors/{uuid}/sync or call run_connector_sync from a worker.",
        "connector_id": request.connector_id,
        "organization_id": str(request.organization_id),
    }


def scheduled_sync_all_connectors(db: Session) -> dict[str, Any]:
    rows = db.query(IntegrationConnector).all()
    results = [run_connector_sync(db, row.id, full_sync=False) for row in rows]
    return {"status": "ok", "count": len(results), "results": results}
