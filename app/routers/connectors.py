"""Connector activation + permission sync — wire Nango + Inngest when persistence exists."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models import (
    AuditAction,
    IntegrationConnector,
    Organization,
    OrganizationMembership,
    OrgMembershipRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.routers.organizations import _write_audit_log
from app.services.billing import ensure_connector_slot, invalidate_plan_cache, register_connector_integration
from app.services.nango_client import normalize_connector_type_for_storage
from app.services.metrics import list_connectors_for_org
from app.services.permissions import sync_permissions
from app.services.rate_limits import enforce_connector_sync_limit
from app.services.sync_orchestrator import run_connector_sync

router = APIRouter(prefix="/connectors", tags=["connectors"])


class ConnectorActivateBody(BaseModel):
    integration_id: str = Field(min_length=1, max_length=128)
    connection_id: str = Field(min_length=1, max_length=512)
    organization_id: UUID | None = None
    workspace_id: UUID | None = Field(default=None, description="Default workspace for sync + ingest")


class PermissionSyncItem(BaseModel):
    document_id: UUID
    organization_id: UUID
    user_id: UUID | None = None
    can_read: bool = True
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=512)


class PermissionSyncBody(BaseModel):
    connector_id: str = Field(min_length=1, max_length=128)
    items: list[PermissionSyncItem]


@router.get("/organization/{organization_id}")
@limiter.exempt
def list_organization_connectors(
    organization_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Connector rows for workspace/admin UIs."""
    _require_connector_view_access(db, organization_id, user)
    return list_connectors_for_org(db, organization_id)


def _org_membership_role(db: Session, org_id: UUID, user_id: UUID) -> str | None:
    row = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == user_id)
        .one_or_none()
    )
    return row.role if row is not None else None


def _has_workspace_role_in_org(db: Session, org_id: UUID, user_id: UUID, allowed_roles: set[str]) -> bool:
    row = (
        db.query(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .filter(
            Workspace.organization_id == org_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role.in_(allowed_roles),
        )
        .first()
    )
    return row is not None


def _require_connector_view_access(db: Session, org_id: UUID, user: User) -> None:
    """View connector state: platform owner, org owner, workspace admin, or editor."""
    if user.is_platform_owner:
        if db.get(Organization, org_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        return
    role = _org_membership_role(db, org_id, user.id)
    if role == OrgMembershipRole.org_owner.value:
        return
    if _has_workspace_role_in_org(
        db,
        org_id,
        user.id,
        {WorkspaceMemberRole.workspace_admin.value, WorkspaceMemberRole.editor.value},
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Connector read access requires admin or editor role")


def _require_connector_manage_access(db: Session, org_id: UUID, user: User) -> None:
    """Manage connectors: platform owner, org owner, or workspace admin."""
    if user.is_platform_owner:
        if db.get(Organization, org_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        return
    role = _org_membership_role(db, org_id, user.id)
    if role == OrgMembershipRole.org_owner.value:
        return
    if _has_workspace_role_in_org(db, org_id, user.id, {WorkspaceMemberRole.workspace_admin.value}):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Connector management requires workspace admin or higher")


@router.post("/activate")
@limiter.exempt
def activate_connector(
    request: Request,
    body: ConnectorActivateBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Called after `Nango.auth()` succeeds in the browser.

    Next: persist `Connector` row, enqueue Inngest job for first sync.
    """
    connector_id_out: str | None = None
    if body.organization_id:
        integration_norm = normalize_connector_type_for_storage(body.integration_id)
        _require_connector_manage_access(db, body.organization_id, user)
        enforce_connector_sync_limit(request, db, body.organization_id, user)
        try:
            ensure_connector_slot(db, body.organization_id)
            register_connector_integration(db, body.organization_id, integration_norm)
            cfg: dict = {}
            if body.workspace_id:
                cfg["workspace_id"] = str(body.workspace_id)
            existing = (
                db.query(IntegrationConnector)
                .filter(
                    IntegrationConnector.organization_id == body.organization_id,
                    IntegrationConnector.connector_type == integration_norm,
                )
                .one_or_none()
            )
            if existing:
                existing.nango_connection_id = body.connection_id
                existing.status = "active"
                if cfg:
                    merged = dict(existing.config or {})
                    merged.update(cfg)
                    existing.config = merged
                persisted = existing
            else:
                persisted = IntegrationConnector(
                    organization_id=body.organization_id,
                    connector_type=integration_norm,
                    nango_connection_id=body.connection_id,
                    status="active",
                    config=cfg or None,
                )
                db.add(persisted)
                db.flush()
            db.commit()
            db.refresh(persisted)
            connector_id_out = str(persisted.id)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Connector integration already registered for this organization",
            ) from None
    return {
        "status": "accepted",
        "integration_id": normalize_connector_type_for_storage(body.integration_id),
        "connection_id": body.connection_id,
        "connector_id": connector_id_out,
        "detail": "Connector row stored; call POST /connectors/{id}/sync to pull documents via Nango.",
    }


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.exempt
def delete_integration_connector(
    connector_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Org owners/workspace admins/platform owners: remove integration row (does not delete ingested docs)."""
    conn = db.get(IntegrationConnector, connector_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    _require_connector_manage_access(db, conn.organization_id, user)
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.connector_deleted.value,
        target_type="integration_connector",
        target_id=conn.id,
        organization_id=conn.organization_id,
        metadata={"connector_type": conn.connector_type},
    )
    invalidate_plan_cache(conn.organization_id)
    db.execute(delete(IntegrationConnector).where(IntegrationConnector.id == connector_id))
    db.commit()


@router.post("/{connector_id}/sync")
@limiter.exempt
def sync_connector_now(
    request: Request,
    connector_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    full_sync: bool = False,
) -> dict:
    """Run a sync: Nango fetch → ingest into default workspace (see connector `config.workspace_id`)."""
    conn = db.get(IntegrationConnector, connector_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    _require_connector_manage_access(db, conn.organization_id, user)
    enforce_connector_sync_limit(request, db, conn.organization_id, user)
    return run_connector_sync(db, connector_id, full_sync=full_sync)


@router.post("/sync-permissions")
@limiter.exempt
def sync_connector_permissions(
    request: Request,
    body: PermissionSyncBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Upsert `DocumentPermission` rows from connector-reported ACLs."""
    if not body.items:
        return {"updated": 0}
    org_id = body.items[0].organization_id
    _require_connector_manage_access(db, org_id, user)
    enforce_connector_sync_limit(request, db, org_id, user)
    raw = [item.model_dump(mode="json") for item in body.items]
    n = sync_permissions(db, body.connector_id, raw)
    return {"updated": n, "connector_id": body.connector_id}
