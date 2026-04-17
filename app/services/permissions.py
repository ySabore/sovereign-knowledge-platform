"""
Document-level RBAC.

- `RBAC_MODE=simple`: workspace members see documents in their assigned workspaces;
  org owners / platform owners may access workspace-scoped docs across their org.
- `RBAC_MODE=full`: only `DocumentPermission` rows grant access; missing row denies access.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentPermission, OrganizationMembership, User, WorkspaceMember
from app.services.rag.types import RetrievalHit

ORG_MEMBERSHIP_ADMIN = "org_owner"
WORKSPACE_ADMIN = "workspace_admin"


def is_organization_member(db: Session, user_id: UUID, organization_id: UUID) -> bool:
    """True if the user has any membership row for this organization."""
    row = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .one_or_none()
    )
    return row is not None


def _is_org_owner(db: Session, user_id: UUID, organization_id: UUID) -> bool:
    row = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == ORG_MEMBERSHIP_ADMIN,
        )
        .one_or_none()
    )
    return row is not None


def _is_workspace_member(db: Session, user_id: UUID, workspace_id: UUID) -> bool:
    row = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user_id, WorkspaceMember.workspace_id == workspace_id)
        .one_or_none()
    )
    return row is not None


def get_accessible_document_ids(
    db: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    workspace_id: UUID,
    user: User | None = None,
) -> set[UUID]:
    """
    Return document IDs the user may retrieve chunks for in this workspace.

    Simple mode: workspace documents for workspace members and org owners.
    Full mode: explicit `DocumentPermission` rows only (org-wide `user_id` NULL or matching user).
    """
    if user and user.is_platform_owner:
        stmt = select(Document.id).where(Document.workspace_id == workspace_id)
        return {row[0] for row in db.execute(stmt).all()}

    mode = settings.rbac_mode.strip().lower()
    if mode != "full":
        if _is_org_owner(db, user_id, organization_id):
            stmt = select(Document.id).where(Document.workspace_id == workspace_id)
            return {row[0] for row in db.execute(stmt).all()}
        if _is_workspace_member(db, user_id, workspace_id):
            stmt = select(Document.id).where(Document.workspace_id == workspace_id)
            return {row[0] for row in db.execute(stmt).all()}
        return set()

    if _is_org_owner(db, user_id, organization_id):
        stmt = select(Document.id).where(Document.workspace_id == workspace_id)
        return {row[0] for row in db.execute(stmt).all()}

    if not _is_workspace_member(db, user_id, workspace_id):
        return set()

    stmt = (
        select(DocumentPermission.document_id)
        .join(Document, Document.id == DocumentPermission.document_id)
        .where(
            Document.workspace_id == workspace_id,
            DocumentPermission.organization_id == organization_id,
            DocumentPermission.can_read.is_(True),
            (DocumentPermission.user_id.is_(None)) | (DocumentPermission.user_id == user_id),
        )
        .distinct()
    )
    return {row[0] for row in db.execute(stmt).all()}


def filter_chunks_by_permission(
    db: Session,
    chunks: list[RetrievalHit],
    *,
    user_id: UUID,
    organization_id: UUID,
    workspace_id: UUID,
    user: User | None = None,
) -> list[RetrievalHit]:
    """Post-retrieval filter; in full mode, chunks whose documents lack permission are removed."""
    allowed = get_accessible_document_ids(
        db,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user=user,
    )
    if settings.rbac_mode.strip().lower() == "full" and not allowed:
        return []
    return [h for h in chunks if h.document_id in allowed]


def has_document_access(
    db: Session,
    *,
    user_id: UUID,
    document_id: UUID,
    user: User | None = None,
) -> bool:
    doc = db.get(Document, document_id)
    if doc is None:
        return False

    if user and user.is_platform_owner:
        return True

    if _is_org_owner(db, user_id, doc.organization_id):
        return True

    if not _is_workspace_member(db, user_id, doc.workspace_id):
        return False

    if settings.rbac_mode.strip().lower() != "full":
        return True

    row = (
        db.query(DocumentPermission)
        .filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.organization_id == doc.organization_id,
            DocumentPermission.can_read.is_(True),
            (DocumentPermission.user_id.is_(None)) | (DocumentPermission.user_id == user_id),
        )
        .one_or_none()
    )
    return row is not None


def sync_permissions(
    db: Session,
    connector_id: str,
    items: list[dict],
) -> int:
    """
    Upsert `DocumentPermission` rows from a connector sync.

    Each item: document_id (UUID str), organization_id (UUID str), user_id (optional UUID str),
    can_read (bool), source (str), external_id (str).
    """
    count = 0
    for raw in items:
        document_id = UUID(str(raw["document_id"]))
        organization_id = UUID(str(raw["organization_id"]))
        user_id = UUID(str(raw["user_id"])) if raw.get("user_id") else None
        can_read = bool(raw.get("can_read", True))
        source = str(raw["source"])
        external_id = str(raw["external_id"])

        existing = (
            db.query(DocumentPermission)
            .filter(
                DocumentPermission.document_id == document_id,
                DocumentPermission.source == source,
                DocumentPermission.external_id == external_id,
            )
            .one_or_none()
        )
        if existing:
            existing.organization_id = organization_id
            existing.user_id = user_id
            existing.can_read = can_read
            existing.connector_id = connector_id
        else:
            db.add(
                DocumentPermission(
                    document_id=document_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    can_read=can_read,
                    source=source,
                    external_id=external_id,
                    connector_id=connector_id,
                )
            )
        count += 1
    db.commit()
    return count


def ensure_upload_permission_row(db: Session, *, document: Document) -> None:
    """In full RBAC mode, grant org-wide read on newly indexed uploads so they remain searchable."""
    if settings.rbac_mode.strip().lower() != "full":
        return
    exists = (
        db.query(DocumentPermission)
        .filter(
            DocumentPermission.document_id == document.id,
            DocumentPermission.source == "upload",
            DocumentPermission.external_id == str(document.id),
        )
        .one_or_none()
    )
    if exists:
        return
    db.add(
        DocumentPermission(
            document_id=document.id,
            organization_id=document.organization_id,
            user_id=None,
            can_read=True,
            source="upload",
            external_id=str(document.id),
            connector_id=None,
        )
    )
    db.flush()


def apply_ingestion_acl(
    db: Session,
    *,
    document: Document,
    source: str,
    external_id: str,
    permission_user_ids: list[UUID] | None,
) -> None:
    """Replace ACL rows for a re-indexed document (full RBAC). Org-wide if `permission_user_ids` is empty."""
    if settings.rbac_mode.strip().lower() != "full":
        return
    db.query(DocumentPermission).filter(DocumentPermission.document_id == document.id).delete()
    db.flush()
    if permission_user_ids:
        for uid in permission_user_ids:
            db.add(
                DocumentPermission(
                    document_id=document.id,
                    organization_id=document.organization_id,
                    user_id=uid,
                    can_read=True,
                    source=source,
                    external_id=f"{external_id}:user:{uid}",
                    connector_id=None,
                )
            )
    else:
        db.add(
            DocumentPermission(
                document_id=document.id,
                organization_id=document.organization_id,
                user_id=None,
                can_read=True,
                source=source,
                external_id=external_id,
                connector_id=None,
            )
        )
    db.flush()
