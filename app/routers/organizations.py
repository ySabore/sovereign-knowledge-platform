import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_platform_owner
from app.models import (
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
    OrganizationPublic,
    OrganizationUpdate,
    WorkspaceCreate,
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

    db.commit()
    db.refresh(org)
    return org


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
    db.commit()
    db.refresh(workspace)
    return workspace
