from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, verify_password
from app.database import get_db
from app.deps import get_current_user
from app.models import OrganizationMembership, OrgMembershipRole, User, Workspace, WorkspaceMember, WorkspaceMemberRole
from app.schemas.auth import LoginRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower().strip()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPublic:
    owner_rows = (
        db.query(OrganizationMembership.organization_id)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .all()
    )
    org_ids_as_owner = [row[0] for row in owner_rows]
    ws_admin_rows = (
        db.query(Workspace.organization_id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.role == WorkspaceMemberRole.workspace_admin.value,
        )
        .distinct()
        .all()
    )
    org_ids_as_workspace_admin = [row[0] for row in ws_admin_rows]
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_platform_owner=user.is_platform_owner,
        org_ids_as_owner=org_ids_as_owner,
        org_ids_as_workspace_admin=org_ids_as_workspace_admin,
    )
