"""Connector activation + permission sync — wire Nango + Inngest when persistence exists."""

from __future__ import annotations

from typing import Any
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
    ConnectorSyncJob,
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
from app.services.nango_client import (
    create_connect_session,
    nango_configured,
    normalize_connector_type_for_storage,
    sanitize_drive_folder_ids,
)
from app.services.metrics import list_connectors_for_org
from app.services.permissions import sync_permissions
from app.services.rate_limits import enforce_connector_sync_limit
from app.services.sync_orchestrator import enqueue_connector_sync_job

router = APIRouter(prefix="/connectors", tags=["connectors"])


class ConnectorActivateBody(BaseModel):
    integration_id: str = Field(min_length=1, max_length=128)
    connection_id: str = Field(min_length=1, max_length=512)
    organization_id: UUID | None = None
    workspace_id: UUID | None = Field(default=None, description="Default workspace for sync + ingest")
    drive_folder_ids: list[str] | None = Field(
        default=None,
        description="Google Drive folder IDs to sync (with subfolders if drive_include_subfolders).",
    )
    drive_include_subfolders: bool | None = Field(
        default=None,
        description="When true (default), recurse into subfolders for drive_folder_ids.",
    )


class ConnectorConfigPatchBody(BaseModel):
    workspace_id: UUID | None = None
    drive_folder_ids: list[str] | None = None
    drive_include_subfolders: bool | None = None


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


class ConnectSessionBody(BaseModel):
    integration_id: str = Field(min_length=1, max_length=128)
    organization_id: UUID


def _workspace_config_ids(cfg: dict | None) -> list[str]:
    if not isinstance(cfg, dict):
        return []
    out: list[str] = []
    raw = cfg.get("workspace_ids")
    if isinstance(raw, list):
        for v in raw:
            s = str(v).strip()
            if not s:
                continue
            try:
                UUID(s)
            except ValueError:
                continue
            if s not in out:
                out.append(s)
    legacy = cfg.get("workspace_id")
    if legacy:
        s = str(legacy).strip()
        try:
            UUID(s)
        except ValueError:
            s = ""
        if s and s not in out:
            out.append(s)
    return out


def _workspace_manage_allowed(db: Session, workspace_id: UUID, user_id: UUID) -> bool:
    row = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role == WorkspaceMemberRole.workspace_admin.value,
        )
        .first()
    )
    return row is not None


def _require_workspace_connector_manage_access(db: Session, org_id: UUID, workspace_id: UUID, user: User) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None or ws.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if user.is_platform_owner:
        return ws
    role = _org_membership_role(db, org_id, user.id)
    if role == OrgMembershipRole.org_owner.value:
        return ws
    if _workspace_manage_allowed(db, workspace_id, user.id):
        return ws
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Connector management requires workspace admin for this workspace or higher",
    )


def _set_connector_workspace_scope(
    conn: IntegrationConnector,
    workspace_ids: list[UUID],
    *,
    preferred_workspace_id: UUID | None,
) -> None:
    cfg = dict(conn.config or {})
    unique_ids = list(dict.fromkeys(str(wid) for wid in workspace_ids))
    if unique_ids:
        cfg["workspace_ids"] = unique_ids
        if preferred_workspace_id is not None:
            cfg["workspace_id"] = str(preferred_workspace_id)
        else:
            cfg["workspace_id"] = unique_ids[0]
    else:
        cfg.pop("workspace_ids", None)
        cfg.pop("workspace_id", None)
    conn.config = cfg or None


def _workspace_settings_map(cfg: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(cfg, dict):
        return {}
    raw = cfg.get("workspace_settings")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if not key or not isinstance(v, dict):
            continue
        out[key] = dict(v)
    return out


def _workspace_drive_sync(cfg: dict[str, Any] | None, workspace_id: UUID | None) -> dict[str, Any]:
    base = dict(cfg or {})
    if workspace_id is not None:
        ws_map = _workspace_settings_map(base)
        ws_cfg = ws_map.get(str(workspace_id))
        if isinstance(ws_cfg, dict):
            if "drive_folder_ids" in ws_cfg:
                base["drive_folder_ids"] = sanitize_drive_folder_ids(ws_cfg.get("drive_folder_ids"))
            if "drive_include_subfolders" in ws_cfg:
                base["drive_include_subfolders"] = bool(ws_cfg.get("drive_include_subfolders"))
    return {
        "folder_ids": sanitize_drive_folder_ids(base.get("drive_folder_ids")),
        "include_subfolders": bool(base.get("drive_include_subfolders", True)),
    }


def _allowed_connector_ids_for_org(db: Session, org_id: UUID) -> set[str] | None:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    raw = org.allowed_connector_ids if isinstance(org.allowed_connector_ids, list) else None
    if not raw:
        return None
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def _require_connector_enabled_for_org(db: Session, org_id: UUID, connector_type: str) -> None:
    allowed = _allowed_connector_ids_for_org(db, org_id)
    if allowed is None:
        return
    if connector_type.strip().lower() in allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This connector is not enabled for the organization.",
    )


def _update_workspace_drive_sync(
    cfg: dict[str, Any],
    *,
    workspace_id: UUID,
    drive_folder_ids: list[str] | None,
    drive_include_subfolders: bool | None,
) -> None:
    ws_map = _workspace_settings_map(cfg)
    scoped = dict(ws_map.get(str(workspace_id)) or {})
    if drive_folder_ids is not None:
        scoped["drive_folder_ids"] = sanitize_drive_folder_ids(drive_folder_ids)
    if drive_include_subfolders is not None:
        scoped["drive_include_subfolders"] = bool(drive_include_subfolders)
    ws_map[str(workspace_id)] = scoped
    if ws_map:
        cfg["workspace_settings"] = ws_map
    else:
        cfg.pop("workspace_settings", None)


def _initialize_workspace_drive_sync(cfg: dict[str, Any], *, workspace_id: UUID) -> None:
    ws_map = _workspace_settings_map(cfg)
    ws_map[str(workspace_id)] = {
        "drive_folder_ids": [],
        "drive_include_subfolders": True,
    }
    cfg["workspace_settings"] = ws_map


def _require_google_drive_workspace_scope(conn: IntegrationConnector, workspace_id: UUID) -> None:
    cfg = conn.config if isinstance(conn.config, dict) else {}
    ws_map = _workspace_settings_map(cfg)
    ws_cfg = ws_map.get(str(workspace_id))
    if not isinstance(ws_cfg, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google Drive folder scope is required before syncing this workspace.",
        )
    folder_ids = sanitize_drive_folder_ids(ws_cfg.get("drive_folder_ids"))
    if folder_ids:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Google Drive folder scope is required before syncing this workspace.",
    )


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


@router.post("/connect-session")
@limiter.exempt
def create_connector_connect_session(
    body: ConnectSessionBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Issue short-lived Nango Connect session token for browser auth popup."""
    integration_norm = normalize_connector_type_for_storage(body.integration_id)
    _require_connector_manage_access(db, body.organization_id, user)
    _require_connector_enabled_for_org(db, body.organization_id, integration_norm)
    if not nango_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NANGO_SECRET_KEY is not configured on the API",
        )
    try:
        session = create_connect_session(
            allowed_integrations=[integration_norm],
            tags={
                "end_user_id": str(user.id),
                "end_user_email": user.email,
                "organization_id": str(body.organization_id),
            },
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "Integration does not exist" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Nango integration '{integration_norm}' is not configured. "
                    "Add/enable this integration in Nango, or mark it as coming soon in connector catalog."
                ),
            ) from None
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create connector auth session: {msg}",
        ) from None
    return {
        "integration_id": integration_norm,
        "token": str(session.get("token")),
        "expires_at": session.get("expires_at"),
        "connect_link": session.get("connect_link"),
    }


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
        _require_connector_enabled_for_org(db, body.organization_id, integration_norm)
        target_workspace_id: UUID | None = None
        if body.workspace_id:
            _require_workspace_connector_manage_access(db, body.organization_id, body.workspace_id, user)
            target_workspace_id = body.workspace_id
        try:
            ensure_connector_slot(db, body.organization_id)
            register_connector_integration(db, body.organization_id, integration_norm)
            cfg: dict = {}
            if target_workspace_id:
                cfg["workspace_id"] = str(target_workspace_id)
                cfg["workspace_ids"] = [str(target_workspace_id)]
            if integration_norm == "google-drive":
                if target_workspace_id and (body.drive_folder_ids is not None or body.drive_include_subfolders is not None):
                    _update_workspace_drive_sync(
                        cfg,
                        workspace_id=target_workspace_id,
                        drive_folder_ids=body.drive_folder_ids,
                        drive_include_subfolders=body.drive_include_subfolders,
                    )
                else:
                    if target_workspace_id:
                        _initialize_workspace_drive_sync(cfg, workspace_id=target_workspace_id)
                    if body.drive_folder_ids is not None:
                        cfg["drive_folder_ids"] = sanitize_drive_folder_ids(body.drive_folder_ids)
                    if body.drive_include_subfolders is not None:
                        cfg["drive_include_subfolders"] = bool(body.drive_include_subfolders)
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
                merged = dict(existing.config or {})
                merged.update(cfg)
                if target_workspace_id:
                    scoped_ids: list[UUID] = []
                    for wid in _workspace_config_ids(merged):
                        try:
                            scoped_ids.append(UUID(wid))
                        except ValueError:
                            continue
                    if target_workspace_id not in scoped_ids:
                        scoped_ids.append(target_workspace_id)
                    merged["workspace_ids"] = [str(wid) for wid in scoped_ids]
                    merged["workspace_id"] = str(target_workspace_id)
                    if integration_norm == "google-drive":
                        _initialize_workspace_drive_sync(merged, workspace_id=target_workspace_id)
                existing.config = merged or None
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


@router.put("/{connector_id}/workspaces/{workspace_id}")
@limiter.exempt
def assign_connector_to_workspace(
    connector_id: UUID,
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Attach an existing connector integration to a workspace scope."""
    conn = db.get(IntegrationConnector, connector_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    _require_workspace_connector_manage_access(db, conn.organization_id, workspace_id, user)
    scoped_ids: list[UUID] = []
    for wid in _workspace_config_ids(conn.config if isinstance(conn.config, dict) else {}):
        try:
            scoped_ids.append(UUID(wid))
        except ValueError:
            continue
    if workspace_id not in scoped_ids:
        scoped_ids.append(workspace_id)
    _set_connector_workspace_scope(conn, scoped_ids, preferred_workspace_id=workspace_id)
    if conn.connector_type == "google-drive":
        merged_cfg = dict(conn.config or {})
        _initialize_workspace_drive_sync(merged_cfg, workspace_id=workspace_id)
        conn.config = merged_cfg
    db.commit()
    db.refresh(conn)
    return {
        "id": str(conn.id),
        "workspace_ids": _workspace_config_ids(conn.config if isinstance(conn.config, dict) else {}),
        "workspace_id": (conn.config or {}).get("workspace_id") if isinstance(conn.config, dict) else None,
    }


@router.delete("/{connector_id}/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.exempt
def remove_connector_from_workspace(
    connector_id: UUID,
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Detach a connector from a workspace; delete row if no workspace remains assigned."""
    conn = db.get(IntegrationConnector, connector_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    _require_workspace_connector_manage_access(db, conn.organization_id, workspace_id, user)
    scoped_ids: list[UUID] = []
    for wid in _workspace_config_ids(conn.config if isinstance(conn.config, dict) else {}):
        try:
            scoped_ids.append(UUID(wid))
        except ValueError:
            continue
    if workspace_id not in scoped_ids:
        return
    remaining = [wid for wid in scoped_ids if wid != workspace_id]
    if not remaining:
        _write_audit_log(
            db,
            actor_user_id=user.id,
            action=AuditAction.connector_deleted.value,
            target_type="integration_connector",
            target_id=conn.id,
            organization_id=conn.organization_id,
            workspace_id=workspace_id,
            metadata={"connector_type": conn.connector_type, "reason": "removed_last_workspace_assignment"},
        )
        invalidate_plan_cache(conn.organization_id)
        db.execute(delete(IntegrationConnector).where(IntegrationConnector.id == connector_id))
        db.commit()
        return
    preferred = None
    cfg = conn.config if isinstance(conn.config, dict) else {}
    current_workspace_raw = cfg.get("workspace_id")
    if current_workspace_raw:
        try:
            current_workspace = UUID(str(current_workspace_raw))
            if current_workspace != workspace_id and current_workspace in remaining:
                preferred = current_workspace
        except ValueError:
            preferred = None
    _set_connector_workspace_scope(conn, remaining, preferred_workspace_id=preferred)
    updated_cfg = dict(conn.config or {})
    ws_settings = _workspace_settings_map(updated_cfg)
    if ws_settings:
        ws_settings.pop(str(workspace_id), None)
        if ws_settings:
            updated_cfg["workspace_settings"] = ws_settings
        else:
            updated_cfg.pop("workspace_settings", None)
    conn.config = updated_cfg or None
    db.commit()


@router.patch("/{connector_id}/config")
@limiter.exempt
def patch_integration_connector_config(
    connector_id: UUID,
    body: ConnectorConfigPatchBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Update connector-specific settings (e.g. Google Drive folder scope)."""
    if body.drive_folder_ids is None and body.drive_include_subfolders is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No config fields to update")
    conn = db.get(IntegrationConnector, connector_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    if body.workspace_id is not None:
        _require_workspace_connector_manage_access(db, conn.organization_id, body.workspace_id, user)
        scoped_ids = _workspace_config_ids(conn.config if isinstance(conn.config, dict) else {})
        if scoped_ids and str(body.workspace_id) not in scoped_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Connector is not enabled for this workspace",
            )
    else:
        _require_connector_manage_access(db, conn.organization_id, user)
    if conn.connector_type != "google-drive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PATCH config is only supported for google-drive connectors",
        )
    merged = dict(conn.config or {})
    if body.workspace_id is not None:
        _update_workspace_drive_sync(
            merged,
            workspace_id=body.workspace_id,
            drive_folder_ids=body.drive_folder_ids,
            drive_include_subfolders=body.drive_include_subfolders,
        )
    else:
        if body.drive_folder_ids is not None:
            merged["drive_folder_ids"] = sanitize_drive_folder_ids(body.drive_folder_ids)
        if body.drive_include_subfolders is not None:
            merged["drive_include_subfolders"] = bool(body.drive_include_subfolders)
    conn.config = merged
    db.commit()
    db.refresh(conn)
    drive_sync = _workspace_drive_sync(merged, body.workspace_id)
    return {
        "id": str(conn.id),
        "connector_type": conn.connector_type,
        "workspace_id": str(body.workspace_id) if body.workspace_id is not None else None,
        "drive_sync": drive_sync,
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
    workspace_id: UUID | None = None,
) -> dict:
    """Enqueue a sync job; worker/background task executes fetch + ingest."""
    conn = db.get(IntegrationConnector, connector_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    if workspace_id is not None:
        _require_workspace_connector_manage_access(db, conn.organization_id, workspace_id, user)
        scoped_ids = _workspace_config_ids(conn.config if isinstance(conn.config, dict) else {})
        if scoped_ids and str(workspace_id) not in scoped_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Connector is not enabled for this workspace",
            )
        if conn.connector_type == "google-drive":
            _require_google_drive_workspace_scope(conn, workspace_id)
    else:
        _require_connector_manage_access(db, conn.organization_id, user)
    enforce_connector_sync_limit(request, db, conn.organization_id, user)
    job, created = enqueue_connector_sync_job(
        db,
        connector_id=connector_id,
        organization_id=conn.organization_id,
        workspace_id=workspace_id,
        requested_by_user_id=user.id,
        full_sync=full_sync,
    )
    return {
        "status": "accepted",
        "detail": "Sync job queued",
        "job_id": str(job.id),
        "job_status": job.status,
        "connector_id": str(connector_id),
        "workspace_id": str(workspace_id) if workspace_id is not None else None,
        "created": created,
    }


@router.get("/sync-jobs/{job_id}")
@limiter.exempt
def get_connector_sync_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Read connector sync job status and latest result metadata."""
    job = db.get(ConnectorSyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync job not found")
    _require_connector_view_access(db, job.organization_id, user)
    return {
        "id": str(job.id),
        "connector_id": str(job.connector_id),
        "organization_id": str(job.organization_id),
        "workspace_id": str(job.workspace_id) if job.workspace_id is not None else None,
        "requested_by_user_id": str(job.requested_by_user_id) if job.requested_by_user_id is not None else None,
        "status": job.status,
        "full_sync": bool(job.full_sync),
        "documents_ingested": int(job.documents_ingested or 0),
        "attempt_count": int(job.attempt_count or 0),
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.post("/sync-permissions")
@limiter.exempt
def sync_connector_permissions(
    body: PermissionSyncBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Upsert `DocumentPermission` rows from connector-reported ACLs."""
    if not body.items:
        return {"updated": 0}
    org_id = body.items[0].organization_id
    _require_connector_manage_access(db, org_id, user)
    raw = [item.model_dump(mode="json") for item in body.items]
    n = sync_permissions(db, body.connector_id, raw)
    return {"updated": n, "connector_id": body.connector_id}
