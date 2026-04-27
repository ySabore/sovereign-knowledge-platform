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

from app.models import ConnectorSyncJob, IntegrationConnector, Organization, Workspace, utcnow
from app.services.ingestion_service import IngestDocumentParams, ingest_document
from app.services.nango_client import DocumentFetchResult, fetch_documents, nango_configured

logger = logging.getLogger(__name__)
SYNC_JOB_QUEUED = "queued"
SYNC_JOB_RUNNING = "running"
SYNC_JOB_COMPLETED = "completed"
SYNC_JOB_FAILED = "failed"


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


def _workspace_effective_config(cfg: dict[str, Any], workspace_id: UUID) -> dict[str, Any]:
    merged = dict(cfg)
    raw = cfg.get("workspace_settings")
    if isinstance(raw, dict):
        ws_cfg = raw.get(str(workspace_id))
        if isinstance(ws_cfg, dict):
            merged.update(ws_cfg)
    return merged


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
    workspace_id_override: UUID | None = None,
) -> dict[str, Any]:
    conn = db.get(IntegrationConnector, connector_row_id)
    if conn is None:
        return {"status": "error", "detail": "connector not found"}

    org = db.get(Organization, conn.organization_id)
    if org is None:
        return {"status": "error", "detail": "organization not found"}

    cfg = conn.config if isinstance(conn.config, dict) else {}
    workspace_id = workspace_id_override or _resolve_workspace_id(db, org.id, cfg)
    if workspace_id is None:
        return {"status": "error", "detail": "No workspace; set config.workspace_id or create a workspace"}
    ws = db.get(Workspace, workspace_id)
    if ws is None or ws.organization_id != org.id:
        return {"status": "error", "detail": "Workspace not found"}

    effective_cfg = _workspace_effective_config(cfg, workspace_id)

    if not nango_configured():
        return {"status": "skipped", "detail": "NANGO_SECRET_KEY not configured"}

    conn.status = "syncing"
    db.commit()

    processed = 0
    errors: list[str] = []
    cursor: str | None = start_cursor
    terminal_status = "active"
    fatal_error: str | None = None

    max_batches = 2000
    batch_idx = 0
    try:
        while True:
            batch, cursor = fetch_documents(
                conn.connector_type,
                conn.nango_connection_id,
                cursor=cursor,
                connector_config=effective_cfg,
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
            batch_idx += 1
            if not cursor:
                break
            if batch_idx >= max_batches:
                logger.warning(
                    "connector sync stopped after max_batches=%s connector_id=%s",
                    max_batches,
                    connector_row_id,
                )
                break
    except Exception as exc:
        logger.exception("connector sync failed: connector_id=%s", connector_row_id)
        terminal_status = "error"
        fatal_error = str(exc)
    finally:
        conn = db.get(IntegrationConnector, connector_row_id)
        if conn:
            conn.last_synced_at = utcnow()
            conn.status = terminal_status
            conn.document_count = processed
            db.commit()

    if fatal_error:
        return {
            "status": "error",
            "connector_id": str(connector_row_id),
            "workspace_id": str(workspace_id),
            "documents_ingested": processed,
            "detail": fatal_error,
            "errors": errors[:50],
        }

    return {
        "status": "ok",
        "connector_id": str(connector_row_id),
        "workspace_id": str(workspace_id),
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


def get_active_sync_job(
    db: Session,
    *,
    connector_id: UUID,
    workspace_id: UUID | None,
) -> ConnectorSyncJob | None:
    q = db.query(ConnectorSyncJob).filter(
        ConnectorSyncJob.connector_id == connector_id,
        ConnectorSyncJob.status.in_([SYNC_JOB_QUEUED, SYNC_JOB_RUNNING]),
    )
    if workspace_id is None:
        q = q.filter(ConnectorSyncJob.workspace_id.is_(None))
    else:
        q = q.filter(ConnectorSyncJob.workspace_id == workspace_id)
    return q.order_by(ConnectorSyncJob.created_at.desc()).first()


def enqueue_connector_sync_job(
    db: Session,
    *,
    connector_id: UUID,
    organization_id: UUID,
    workspace_id: UUID | None,
    requested_by_user_id: UUID | None,
    full_sync: bool,
) -> tuple[ConnectorSyncJob, bool]:
    existing = get_active_sync_job(db, connector_id=connector_id, workspace_id=workspace_id)
    if existing is not None:
        return existing, False
    job = ConnectorSyncJob(
        connector_id=connector_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        requested_by_user_id=requested_by_user_id,
        full_sync=bool(full_sync),
        status=SYNC_JOB_QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def run_connector_sync_job(db: Session, job_id: UUID, *, claimed: bool = False) -> dict[str, Any]:
    job = db.get(ConnectorSyncJob, job_id)
    if job is None:
        return {"status": "error", "detail": "sync job not found", "job_id": str(job_id)}
    if job.status == SYNC_JOB_RUNNING and not claimed:
        return {"status": "accepted", "detail": "sync job already running", "job_id": str(job.id)}
    if job.status in (SYNC_JOB_COMPLETED, SYNC_JOB_FAILED):
        return {
            "status": "accepted",
            "detail": "sync job already finalized",
            "job_id": str(job.id),
            "job_status": job.status,
        }

    if not claimed:
        job.status = SYNC_JOB_RUNNING
        job.started_at = utcnow()
        job.finished_at = None
        job.error_message = None
        job.attempt_count = int(job.attempt_count or 0) + 1
        db.commit()

    try:
        result = run_connector_sync(
            db,
            job.connector_id,
            full_sync=job.full_sync,
            workspace_id_override=job.workspace_id,
        )
        ok = result.get("status") == "ok"
        job = db.get(ConnectorSyncJob, job_id)
        if job is not None:
            job.status = SYNC_JOB_COMPLETED if ok else SYNC_JOB_FAILED
            job.documents_ingested = int(result.get("documents_ingested") or 0)
            job.error_message = None if ok else str(result.get("detail") or "sync failed")
            job.finished_at = utcnow()
            db.commit()
        return result
    except Exception as exc:
        logger.exception("run_connector_sync_job failed: job_id=%s", job_id)
        job = db.get(ConnectorSyncJob, job_id)
        if job is not None:
            job.status = SYNC_JOB_FAILED
            job.error_message = str(exc)
            job.finished_at = utcnow()
            db.commit()
        return {"status": "error", "detail": str(exc), "job_id": str(job_id)}


def claim_next_connector_sync_job(db: Session) -> ConnectorSyncJob | None:
    """Atomically claim the oldest queued job using row locking."""
    row = (
        db.query(ConnectorSyncJob)
        .filter(ConnectorSyncJob.status == SYNC_JOB_QUEUED)
        .order_by(ConnectorSyncJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if row is None:
        return None
    row.status = SYNC_JOB_RUNNING
    row.started_at = utcnow()
    row.finished_at = None
    row.error_message = None
    row.attempt_count = int(row.attempt_count or 0) + 1
    db.commit()
    db.refresh(row)
    return row


def scheduled_sync_all_connectors(db: Session) -> dict[str, Any]:
    rows = db.query(IntegrationConnector).all()
    results = [run_connector_sync(db, row.id, full_sync=False) for row in rows]
    return {"status": "ok", "count": len(results), "results": results}
