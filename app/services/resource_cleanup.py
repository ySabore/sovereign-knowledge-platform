"""Remove stored files and issue bulk deletes that rely on DB CASCADE for related rows.

Artifact unlinks must run only after a successful DB commit. Deleting storage before
commit risks permanent data loss when the transaction rolls back (document rows would
still point at missing files). Prefer orphaned blobs over broken DB references.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Document, Organization, Workspace
from app.services.billing import invalidate_plan_cache
from app.services.storage import get_storage_backend

logger = logging.getLogger(__name__)


def _unlink_storage_path(storage_path: str | None) -> None:
    if not storage_path or not str(storage_path).strip():
        return
    try:
        get_storage_backend().delete_by_uri(storage_path)
    except Exception as exc:
        logger.warning("Could not delete stored file %s: %s", storage_path, exc)


def unlink_storage_paths(storage_paths: Iterable[str | None]) -> None:
    """Best-effort artifact cleanup after a durable DB commit."""
    for path in storage_paths:
        _unlink_storage_path(path)


def collect_document_storage_path(db: Session, document_id: UUID) -> str | None:
    return db.scalar(select(Document.storage_path).where(Document.id == document_id))


def collect_document_storage_paths_for_organization(db: Session, organization_id: UUID) -> list[str]:
    paths = db.scalars(select(Document.storage_path).where(Document.organization_id == organization_id)).all()
    return [p for p in paths if p and str(p).strip()]


def collect_document_storage_paths_for_workspace(db: Session, workspace_id: UUID) -> list[str]:
    paths = db.scalars(select(Document.storage_path).where(Document.workspace_id == workspace_id)).all()
    return [p for p in paths if p and str(p).strip()]


def unlink_document_files_for_organization(db: Session, organization_id: UUID) -> int:
    """Deprecated for pre-commit use; prefer collect + post-commit unlink_storage_paths."""
    paths = collect_document_storage_paths_for_organization(db, organization_id)
    unlink_storage_paths(paths)
    return len(paths)


def unlink_document_files_for_workspace(db: Session, workspace_id: UUID) -> int:
    """Deprecated for pre-commit use; prefer collect + post-commit unlink_storage_paths."""
    paths = collect_document_storage_paths_for_workspace(db, workspace_id)
    unlink_storage_paths(paths)
    return len(paths)


def unlink_document_file(db: Session, document_id: UUID) -> None:
    """Deprecated for pre-commit use; prefer collect + post-commit unlink_storage_paths."""
    unlink_storage_paths([collect_document_storage_path(db, document_id)])


def delete_organization_cascade(db: Session, organization_id: UUID) -> list[str]:
    """Delete the organization row (CASCADE related data). Return storage paths to unlink after commit."""
    paths = collect_document_storage_paths_for_organization(db, organization_id)
    invalidate_plan_cache(organization_id)
    db.execute(delete(Organization).where(Organization.id == organization_id))
    return paths


def delete_workspace_cascade(db: Session, workspace_id: UUID) -> list[str]:
    """Delete the workspace row (CASCADE related data). Return storage paths to unlink after commit."""
    paths = collect_document_storage_paths_for_workspace(db, workspace_id)
    db.execute(delete(Workspace).where(Workspace.id == workspace_id))
    return paths
