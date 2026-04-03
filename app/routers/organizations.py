import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_platform_owner
from app.models import (
    AuditAction,
    AuditLog,
    Organization,
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.schemas.auth import (
    OrganizationCreate,
    OrganizationMemberPublic,
    OrganizationMemberUpsert,
    OrganizationPublic,
    OrganizationUpdate,
    WorkspaceCreate,
    WorkspaceMemberPublic,
    WorkspaceMemberUpsert,
    WorkspacePublic,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])
router_w = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _get_org_membership(db: Session, org_id: UUID, user_id: UUID) -> OrganizationMembership | None:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
        .one_or_none()
    )


def _require_org_membership(db: Session, org_id: UUID, user: User) -> OrganizationMembership:
    membership = _get_org_membership(db, org_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return membership


def _require_org_owner(db: Session, org_id: UUID, user: User) -> OrganizationMembership:
    membership = _require_org_membership(db, org_id, user)
    if membership.role != OrgMembershipRole.org_owner.value:
        raise HTTPException(status_code=403, detail="Org owner role required")
    return membership


def _count_org_owners(db: Session, org_id: UUID) -> int:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .count()
    )


def _serialize_org_member(membership: OrganizationMembership) -> OrganizationMemberPublic:
    return OrganizationMemberPublic(
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
    )


def _serialize_workspace_member(membership: WorkspaceMember) -> WorkspaceMemberPublic:
    return WorkspaceMemberPublic(
        user_id=membership.user_id,
        workspace_id=membership.workspace_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
    )


def _get_workspace_for_user(db: Session, workspace_id: UUID, user_id: UUID) -> Workspace | None:
    return (
        db.query(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
        .one_or_none()
    )


def _require_workspace_admin(db: Session, workspace_id: UUID, user: User) -> Workspace:
    workspace = _get_workspace_for_user(db, workspace_id, user.id)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .one()
    )
    if membership.role != WorkspaceMemberRole.workspace_admin.value:
        raise HTTPException(status_code=403, detail="Workspace admin role required")
    return workspace


def _count_workspace_admins(db: Session, workspace_id: UUID) -> int:
    return (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == WorkspaceMemberRole.workspace_admin.value,
        )
        .count()
    )


def _get_active_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email.lower().strip()).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    return user


def _write_audit_log(
    db: Session,
    *,
    actor_user_id: UUID | None,
    action: str,
    target_type: str,
    target_id: UUID | None,
    organization_id: UUID | None = None,
    workspace_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata,
        )
    )


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrganizationCreate,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
) -> Organization:
    slug = body.slug.strip().lower()
    exists = db.query(Organization).filter(Organization.slug == slug).one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Slug already in use")
    org = Organization(
        name=body.name.strip(),
        slug=slug,
        tenant_key=secrets.token_urlsafe(16),
        status=OrgStatus.active.value,
    )
    db.add(org)
    db.flush()
    db.add(
        OrganizationMembership(
            user_id=owner.id,
            organization_id=org.id,
            role=OrgMembershipRole.org_owner.value,
        )
    )
    _write_audit_log(
        db,
        actor_user_id=owner.id,
        action=AuditAction.organization_created.value,
        target_type="organization",
        target_id=org.id,
        organization_id=org.id,
        metadata={"slug": org.slug, "status": org.status},
    )
    db.commit()
    db.refresh(org)
    return org


@router.get("/me", response_model=list[OrganizationPublic])
def list_my_organizations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Organization]:
    q = (
        db.query(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .filter(OrganizationMembership.user_id == user.id)
        .order_by(Organization.created_at.asc())
    )
    return list(q.all())


@router.get("/{org_id}", response_model=OrganizationPublic)
def get_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Organization:
    _require_org_membership(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/{org_id}/members", response_model=list[OrganizationMemberPublic])
def list_organization_members(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrganizationMemberPublic]:
    _require_org_membership(db, org_id, user)
    memberships = (
        db.query(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == org_id)
        .order_by(OrganizationMembership.created_at.asc())
        .all()
    )
    return [_serialize_org_member(membership) for membership in memberships]


@router.put("/{org_id}/members", response_model=OrganizationMemberPublic)
def upsert_organization_member(
    org_id: UUID,
    body: OrganizationMemberUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationMemberPublic:
    _require_org_owner(db, org_id, user)
    normalized_role = body.role.strip().lower()
    allowed_roles = {role.value for role in OrgMembershipRole}
    if normalized_role not in allowed_roles:
        raise HTTPException(status_code=422, detail=f"Invalid role. Allowed: {sorted(allowed_roles)}")

    target_user = _get_active_user_by_email(db, body.email)
    membership = _get_org_membership(db, org_id, target_user.id)
    if membership is None:
        membership = OrganizationMembership(
            user_id=target_user.id,
            organization_id=org_id,
            role=normalized_role,
        )
        db.add(membership)
    else:
        membership.role = normalized_role

    db.flush()
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_member_upserted.value,
        target_type="organization_membership",
        target_id=membership.id,
        organization_id=org_id,
        metadata={"member_user_id": str(target_user.id), "email": target_user.email, "role": normalized_role},
    )
    db.commit()
    db.refresh(membership)
    return _serialize_org_member(membership)


@router.patch("/{org_id}", response_model=OrganizationPublic)
def update_organization(
    org_id: UUID,
    body: OrganizationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Organization:
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.name is not None:
        org.name = body.name.strip()
    if body.status is not None:
        normalized_status = body.status.strip().lower()
        allowed_statuses = {status.value for status in OrgStatus}
        if normalized_status not in allowed_statuses:
            raise HTTPException(status_code=422, detail=f"Invalid status. Allowed: {sorted(allowed_statuses)}")
        org.status = normalized_status

    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_updated.value,
        target_type="organization",
        target_id=org.id,
        organization_id=org.id,
        metadata={"name": org.name, "status": org.status},
    )
    db.commit()
    db.refresh(org)
    return org


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_organization_member(
    org_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _require_org_owner(db, org_id, user)
    membership = _get_org_membership(db, org_id, user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization member not found")
    if membership.role == OrgMembershipRole.org_owner.value and _count_org_owners(db, org_id) <= 1:
        raise HTTPException(status_code=409, detail="Cannot remove the last organization owner")

    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_member_removed.value,
        target_type="organization_membership",
        target_id=membership.id,
        organization_id=org_id,
        metadata={"member_user_id": str(membership.user_id), "role": membership.role},
    )
    db.delete(membership)
    db.commit()


@router_w.post("/org/{org_id}", response_model=WorkspacePublic, status_code=status.HTTP_201_CREATED)
def create_workspace(
    org_id: UUID,
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Workspace:
    _require_org_owner(db, org_id, user)
    ws = Workspace(
        organization_id=org_id,
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=ws.id,
            user_id=user.id,
            role=WorkspaceMemberRole.workspace_admin.value,
        )
    )
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.workspace_created.value,
        target_type="workspace",
        target_id=ws.id,
        organization_id=org_id,
        workspace_id=ws.id,
        metadata={"name": ws.name},
    )
    db.commit()
    db.refresh(ws)
    return ws


@router_w.get("/org/{org_id}", response_model=list[WorkspacePublic])
def list_workspaces(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Workspace]:
    _require_org_membership(db, org_id, user)
    rows = db.query(Workspace).filter(Workspace.organization_id == org_id).order_by(Workspace.created_at.asc()).all()
    return list(rows)


@router_w.get("/me", response_model=list[WorkspacePublic])
def list_my_workspaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Workspace]:
    rows = (
        db.query(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at.asc())
        .all()
    )
    return list(rows)


@router_w.get("/{workspace_id}", response_model=WorkspacePublic)
def get_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Workspace:
    workspace = _get_workspace_for_user(db, workspace_id, user.id)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    return workspace


@router_w.get("/{workspace_id}/members", response_model=list[WorkspaceMemberPublic])
def list_workspace_members(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkspaceMemberPublic]:
    workspace = _get_workspace_for_user(db, workspace_id, user.id)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    memberships = (
        db.query(WorkspaceMember)
        .join(User, User.id == WorkspaceMember.user_id)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
        .all()
    )
    return [_serialize_workspace_member(membership) for membership in memberships]


@router_w.put("/{workspace_id}/members", response_model=WorkspaceMemberPublic)
def upsert_workspace_member(
    workspace_id: UUID,
    body: WorkspaceMemberUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkspaceMemberPublic:
    workspace = _require_workspace_admin(db, workspace_id, user)
    normalized_role = body.role.strip().lower()
    allowed_roles = {role.value for role in WorkspaceMemberRole}
    if normalized_role not in allowed_roles:
        raise HTTPException(status_code=422, detail=f"Invalid role. Allowed: {sorted(allowed_roles)}")

    target_user = _get_active_user_by_email(db, body.email)
    _require_org_membership(db, workspace.organization_id, target_user)
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == target_user.id)
        .one_or_none()
    )
    if membership is None:
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=normalized_role,
        )
        db.add(membership)
    else:
        membership.role = normalized_role

    db.flush()
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.workspace_member_upserted.value,
        target_type="workspace_membership",
        target_id=membership.id,
        organization_id=workspace.organization_id,
        workspace_id=workspace_id,
        metadata={"member_user_id": str(target_user.id), "email": target_user.email, "role": normalized_role},
    )
    db.commit()
    db.refresh(membership)
    return _serialize_workspace_member(membership)


@router_w.patch("/{workspace_id}", response_model=WorkspacePublic)
def update_workspace(
    workspace_id: UUID,
    body: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Workspace:
    workspace = _require_workspace_admin(db, workspace_id, user)
    if body.name is not None:
        workspace.name = body.name.strip()
    if body.description is not None:
        workspace.description = body.description.strip() or None
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.workspace_updated.value,
        target_type="workspace",
        target_id=workspace.id,
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        metadata={"name": workspace.name, "description": workspace.description},
    )
    db.commit()
    db.refresh(workspace)
    return workspace


@router_w.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _require_workspace_admin(db, workspace_id, user)
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if membership.role == WorkspaceMemberRole.workspace_admin.value and _count_workspace_admins(db, workspace_id) <= 1:
        raise HTTPException(status_code=409, detail="Cannot remove the last workspace admin")

    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.workspace_member_removed.value,
        target_type="workspace_membership",
        target_id=membership.id,
        workspace_id=workspace_id,
        metadata={"member_user_id": str(membership.user_id), "role": membership.role},
    )
    db.delete(membership)
    db.commit()
