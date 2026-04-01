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
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.schemas.auth import OrganizationCreate, OrganizationPublic, WorkspaceCreate, WorkspacePublic

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrganizationCreate,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
) -> Organization:
    exists = db.query(Organization).filter(Organization.slug == body.slug).one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Slug already in use")
    org = Organization(
        name=body.name.strip(),
        slug=body.slug.strip().lower(),
        tenant_key=secrets.token_urlsafe(16),
        status="active",
    )
    db.add(org)
    db.flush()
    # Creator becomes org_owner membership if not already system-linked; platform owner may not be in org — add org_owner as first member from a separate flow in Phase 2. For Phase 1, attach platform owner as org_owner.
    m = OrganizationMembership(
        user_id=owner.id,
        organization_id=org.id,
        role=OrgMembershipRole.org_owner.value,
    )
    db.add(m)
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
    )
    return list(q.all())


router_w = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router_w.post("/org/{org_id}", response_model=WorkspacePublic, status_code=status.HTTP_201_CREATED)
def create_workspace(
    org_id: UUID,
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Workspace:
    m = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
        )
        .one_or_none()
    )
    if m is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    if m.role not in (OrgMembershipRole.org_owner.value,):
        raise HTTPException(status_code=403, detail="Org owner role required to create workspace")
    ws = Workspace(
        organization_id=org_id,
        name=body.name.strip(),
        description=body.description,
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    wm = WorkspaceMember(
        workspace_id=ws.id,
        user_id=user.id,
        role=WorkspaceMemberRole.workspace_admin.value,
    )
    db.add(wm)
    db.commit()
    db.refresh(ws)
    return ws


@router_w.get("/org/{org_id}", response_model=list[WorkspacePublic])
def list_workspaces(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Workspace]:
    m = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
        )
        .one_or_none()
    )
    if m is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    rows = db.query(Workspace).filter(Workspace.organization_id == org_id).all()
    return list(rows)
