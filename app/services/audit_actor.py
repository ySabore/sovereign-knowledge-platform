"""Resolve actor role strings for audit log rows (compliance / SOX-style trails)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    OrganizationMembership,
    OrgMembershipRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)


def infer_actor_role(
    db: Session,
    user: User,
    *,
    organization_id: UUID | None,
    workspace_id: UUID | None,
) -> str | None:
    """Best-effort role label at the time of the event."""
    if user.is_platform_owner:
        return "platform_owner"

    org_id = organization_id
    if org_id is None and workspace_id is not None:
        ws = db.get(Workspace, workspace_id)
        org_id = ws.organization_id if ws is not None else None

    org_membership: OrganizationMembership | None = None
    if org_id is not None:
        org_membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.user_id == user.id,
            )
            .one_or_none()
        )

    if workspace_id is not None:
        wm = (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
            .one_or_none()
        )
        if wm is not None:
            if wm.role == WorkspaceMemberRole.workspace_admin.value:
                return "workspace_admin"
            if wm.role == WorkspaceMemberRole.editor.value:
                return "workspace_editor"
            if wm.role == WorkspaceMemberRole.member.value:
                return "workspace_member"

    if org_membership is not None:
        if org_membership.role == OrgMembershipRole.org_owner.value:
            return "org_owner"
        if org_membership.role == OrgMembershipRole.member.value:
            return "org_member"

    return None
