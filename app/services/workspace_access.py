"""Workspace visibility for chat/uploads: platform owner, org owner, or assigned workspace member."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import OrganizationMembership, OrgMembershipRole, User, Workspace, WorkspaceMember


def resolve_workspace_for_user(db: Session, workspace_id: UUID, user: User) -> Workspace | None:
    """
    Return the workspace if the user may access it.

    - Platform owners: any workspace by id.
    - Otherwise: workspace member, or org owner for the workspace's organization.
    """
    if user.is_platform_owner:
        return db.get(Workspace, workspace_id)
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        return None
    in_ws = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )
    if in_ws is not None:
        return ws
    org_owner_membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == ws.organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .one_or_none()
    )
    if org_owner_membership is not None:
        return ws
    return None
