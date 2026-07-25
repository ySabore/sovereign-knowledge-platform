"""Workspace visibility for chat/uploads: platform owner, org owner, or assigned workspace member."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    OrganizationMembership,
    OrgMembershipRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)


def resolve_workspace_for_user(db: Session, workspace_id: UUID, user: User) -> Workspace | None:
    """
    Return the workspace if the user may access it.

    - Platform owners: any workspace by id.
    - Otherwise: active org member who is either a workspace member, or an org owner
      for the workspace's organization.
    """
    if user.is_platform_owner:
        return db.get(Workspace, workspace_id)
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        return None

    org_membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == ws.organization_id,
            OrganizationMembership.user_id == user.id,
        )
        .one_or_none()
    )
    if org_membership is None:
        return None
    if org_membership.role == OrgMembershipRole.org_owner.value:
        return ws

    in_ws = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )
    if in_ws is not None:
        return ws
    return None


def require_workspace_contributor(db: Session, workspace_id: UUID, user: User) -> Workspace:
    """Require editor/workspace_admin (or org/platform owner) for upload/write paths."""
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if user.is_platform_owner:
        return workspace

    org_membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == workspace.organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .one_or_none()
    )
    if org_membership is not None:
        return workspace

    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if membership.role not in {
        WorkspaceMemberRole.workspace_admin.value,
        WorkspaceMemberRole.editor.value,
    }:
        raise HTTPException(status_code=403, detail="Workspace contributor role required")
    return workspace
