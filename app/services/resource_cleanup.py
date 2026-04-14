"""Remove stored files and issue bulk deletes that rely on DB CASCADE for related rows."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Document, Organization, Workspace
from app.services.billing import invalidate_plan_cache

logger = logging.getLogger(__name__)


def _unlink_storage_path(storage_path: str | None) -> None:
    if not storage_path or not str(storage_path).strip():
        return
    try:
        p = Path(storage_path)
        if p.is_file():
            p.unlink()
    except OSError as exc:
        logger.warning("Could not delete stored file %s: %s", storage_path, exc)


def unlink_document_files_for_organization(db: Session, organization_id: UUID) -> int:
    paths = db.scalars(select(Document.storage_path).where(Document.organization_id == organization_id)).all()
    for path in paths:
        _unlink_storage_path(path)
    return len(paths)


def unlink_document_files_for_workspace(db: Session, workspace_id: UUID) -> int:
    paths = db.scalars(select(Document.storage_path).where(Document.workspace_id == workspace_id)).all()
    for path in paths:
        _unlink_storage_path(path)
    return len(paths)


def unlink_document_file(db: Session, document_id: UUID) -> None:
    path = db.scalar(select(Document.storage_path).where(Document.id == document_id))
    _unlink_storage_path(path)


def delete_organization_cascade(db: Session, organization_id: UUID) -> None:
    unlink_document_files_for_organization(db, organization_id)
    invalidate_plan_cache(organization_id)
    db.execute(delete(Organization).where(Organization.id == organization_id))


def delete_workspace_cascade(db: Session, workspace_id: UUID) -> None:
    unlink_document_files_for_workspace(db, workspace_id)
    db.execute(delete(Workspace).where(Workspace.id == workspace_id))
