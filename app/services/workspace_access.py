"""Workspace visibility for chat/uploads: platform owner, workspace member, or org member (simple RBAC)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.services.permissions import is_organization_member


def resolve_workspace_for_user(db: Session, workspace_id: UUID, user: User) -> Workspace | None:
    """
    Return the workspace if the user may access it.

    - Platform owners: any workspace by id.
    - Otherwise: workspace member, or any member of the workspace's organization (simple mode UX).
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
    if is_organization_member(db, user.id, ws.organization_id):
        return ws
    return None
