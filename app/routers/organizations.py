import secrets
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.deps import get_current_user, require_platform_owner
from app.limiter import limiter
from app.models import (
    AuditAction,
    AuditLog,
    ChatSession,
    Document,
    Organization,
    OrganizationMembership,
    OrganizationInvite,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.services.audit_actor import infer_actor_role
from app.services.billing import ensure_seat_available, get_plan_entitlements
from app.services.metrics import list_audit_events_for_org, list_documents_for_org
from app.services.field_encryption import encrypt_org_secret
from app.services.invite_email import send_organization_invite_email
from app.services.resource_cleanup import delete_organization_cascade, delete_workspace_cascade
from app.services.rate_limits import enforce_privileged_read_api_limit
from app.services.workspace_access import resolve_workspace_for_user
from app.schemas.auth import (
    OrganizationCreate,
    OrganizationMemberPublic,
    OrganizationMemberUpsert,
    OrganizationInviteAcceptRequest,
    OrganizationInviteCreate,
    OrganizationInviteIssueResponse,
    OrganizationInvitePublic,
    OrganizationOverviewStats,
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

DEFAULT_WORKSPACE_NAME = "General"
DEFAULT_WORKSPACE_DESCRIPTION = "Default workspace created with the organization."
INVITE_TTL_DAYS = 7
logger = logging.getLogger(__name__)


def _normalize_allowed_connector_ids(raw: object) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="allowed_connector_ids must be an array of connector ids or null.",
        )
    valid_catalog_ids = {
        str(item.get("id")).strip().lower()
        for item in settings.connector_catalog()
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    normalized: list[str] = []
    for item in raw:
        connector_id = str(item or "").strip().lower()
        if not connector_id:
            continue
        if connector_id not in valid_catalog_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown connector id '{connector_id}'.",
            )
        if connector_id not in normalized:
            normalized.append(connector_id)
    return normalized or None


def _get_org_membership(db: Session, org_id: UUID, user_id: UUID) -> OrganizationMembership | None:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
        .one_or_none()
    )


def _require_org_membership(
    db: Session,
    org_id: UUID,
    user: User,
    *,
    allow_platform_owner_bypass: bool = True,
) -> OrganizationMembership | None:
    """
    Require org membership, or (for the signed-in platform owner only) allow access to any org that exists.
    Use allow_platform_owner_bypass=False when validating another user (e.g. workspace invitee) who must be a member.
    """
    membership = _get_org_membership(db, org_id, user.id)
    if membership is not None:
        return membership
    if allow_platform_owner_bypass and user.is_platform_owner:
        org = db.get(Organization, org_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return None
    raise HTTPException(status_code=403, detail="Not a member of this organization")


def _require_org_owner(db: Session, org_id: UUID, user: User) -> OrganizationMembership | None:
    if user.is_platform_owner:
        return None
    membership = _require_org_membership(db, org_id, user, allow_platform_owner_bypass=False)
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


def _serialize_org_invite(invite: OrganizationInvite) -> OrganizationInvitePublic:
    return OrganizationInvitePublic(
        id=invite.id,
        organization_id=invite.organization_id,
        email=invite.email,
        role=invite.role,
        status=invite.status,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        created_at=invite.created_at,
    )


def _issue_invite_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, token_hash


def _ensure_default_workspace_membership(db: Session, org_id: UUID, target_user_id: UUID, org_role: str) -> None:
    default_ws = (
        db.query(Workspace)
        .filter(Workspace.organization_id == org_id, Workspace.name == DEFAULT_WORKSPACE_NAME)
        .one_or_none()
    )
    if default_ws is None:
        return
    desired_ws_role = (
        WorkspaceMemberRole.workspace_admin.value
        if org_role == OrgMembershipRole.org_owner.value
        else WorkspaceMemberRole.member.value
    )
    ws_membership = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == default_ws.id,
            WorkspaceMember.user_id == target_user_id,
        )
        .one_or_none()
    )
    if ws_membership is None:
        db.add(
            WorkspaceMember(
                workspace_id=default_ws.id,
                user_id=target_user_id,
                role=desired_ws_role,
            )
        )
    else:
        ws_membership.role = desired_ws_role
        db.add(ws_membership)


def _require_workspace_admin(db: Session, workspace_id: UUID, user: User) -> Workspace:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if user.is_platform_owner:
        return workspace
    org_membership = _get_org_membership(db, workspace.organization_id, user.id)
    if org_membership is not None and org_membership.role == OrgMembershipRole.org_owner.value:
        return workspace
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .one()
    )
    if membership.role != WorkspaceMemberRole.workspace_admin.value:
        raise HTTPException(status_code=403, detail="Workspace admin role required")
    return workspace


def _workspace_admin_workspace_ids_in_org(db: Session, org_id: UUID, user_id: UUID) -> list[UUID]:
    rows = (
        db.query(WorkspaceMember.workspace_id)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .filter(
            Workspace.organization_id == org_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role == WorkspaceMemberRole.workspace_admin.value,
        )
        .all()
    )
    return [row[0] for row in rows]


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
    actor_role: str | None = None,
) -> None:
    resolved_role = actor_role
    if resolved_role is None and actor_user_id is not None:
        actor = db.get(User, actor_user_id)
        if actor is not None:
            resolved_role = infer_actor_role(
                db, actor, organization_id=organization_id, workspace_id=workspace_id
            )
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            actor_role=resolved_role,
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
    if body.preferred_chat_provider is not None:
        raw_p = body.preferred_chat_provider
        s = str(raw_p).strip().lower()
        if s in ("", "inherit", "platform", "default"):
            org.preferred_chat_provider = None
        elif s in ("extractive", "ollama", "openai", "anthropic"):
            org.preferred_chat_provider = s
        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid preferred_chat_provider. Use extractive, ollama, openai, anthropic, "
                    "or omit for platform default."
                ),
            )
    if body.preferred_chat_model is not None:
        org.preferred_chat_model = (str(body.preferred_chat_model) or "").strip() or None
    if body.ollama_base_url is not None:
        org.ollama_base_url = (str(body.ollama_base_url).strip() or None)

    db.add(org)
    db.flush()
    db.add(
        OrganizationMembership(
            user_id=owner.id,
            organization_id=org.id,
            role=OrgMembershipRole.org_owner.value,
        )
    )

    # Always provision a default workspace and membership so every org starts usable.
    ws = Workspace(
        organization_id=org.id,
        name=DEFAULT_WORKSPACE_NAME,
        description=DEFAULT_WORKSPACE_DESCRIPTION,
        created_by=owner.id,
    )
    db.add(ws)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=ws.id,
            user_id=owner.id,
            role=WorkspaceMemberRole.workspace_admin.value,
        )
    )
    # Create an initial chat session for the creator in the default workspace.
    # Note: chat sessions are per-user in the current model.
    db.add(
        ChatSession(
            organization_id=org.id,
            workspace_id=ws.id,
            user_id=owner.id,
            title="General",
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
    _write_audit_log(
        db,
        actor_user_id=owner.id,
        action=AuditAction.workspace_created.value,
        target_type="workspace",
        target_id=ws.id,
        organization_id=org.id,
        workspace_id=ws.id,
        metadata={"name": ws.name},
    )
    _write_audit_log(
        db,
        actor_user_id=owner.id,
        action=AuditAction.workspace_member_upserted.value,
        target_type="workspace_member",
        target_id=owner.id,
        organization_id=org.id,
        workspace_id=ws.id,
        metadata={"role": WorkspaceMemberRole.workspace_admin.value},
    )
    db.commit()
    db.refresh(org)
    return org


@router.get("/me", response_model=list[OrganizationPublic])
@limiter.exempt
def list_my_organizations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Organization]:
    if user.is_platform_owner:
        rows = list(db.query(Organization).order_by(Organization.created_at.asc()).all())
        allow = settings.platform_owner_visible_org_slug_set()
        if allow is not None:
            rows = [o for o in rows if o.slug.lower() in allow]
        return rows
    q = (
        db.query(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .filter(OrganizationMembership.user_id == user.id)
        .order_by(Organization.created_at.asc())
    )
    return list(q.all())


@router.get("/{org_id}/invites", response_model=list[OrganizationInvitePublic])
def list_organization_invites(
    org_id: UUID,
    status_filter: str | None = "pending",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrganizationInvitePublic]:
    _require_org_owner(db, org_id, user)
    q = db.query(OrganizationInvite).filter(OrganizationInvite.organization_id == org_id)
    if status_filter:
        q = q.filter(OrganizationInvite.status == status_filter)
    rows = q.order_by(OrganizationInvite.created_at.desc()).all()
    return [_serialize_org_invite(r) for r in rows]


@router.post("/{org_id}/invites", response_model=OrganizationInviteIssueResponse, status_code=status.HTTP_201_CREATED)
def create_organization_invite(
    org_id: UUID,
    body: OrganizationInviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationInviteIssueResponse:
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    normalized_role = body.role.strip().lower()
    allowed_roles = {role.value for role in OrgMembershipRole}
    if normalized_role not in allowed_roles:
        raise HTTPException(status_code=422, detail=f"Invalid role. Allowed: {sorted(allowed_roles)}")

    normalized_email = body.email.strip().lower()
    existing_user = db.query(User).filter(User.email == normalized_email).one_or_none()
    if existing_user:
        existing_membership = _get_org_membership(db, org_id, existing_user.id)
        if existing_membership is not None:
            raise HTTPException(status_code=409, detail="User is already an organization member")

    token, token_hash = _issue_invite_token()
    invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.email == normalized_email,
            OrganizationInvite.status == "pending",
        )
        .order_by(OrganizationInvite.created_at.desc())
        .first()
    )
    action = AuditAction.organization_invite_sent.value
    if invite is None:
        invite = OrganizationInvite(
            organization_id=org_id,
            email=normalized_email,
            role=normalized_role,
            status="pending",
            invite_token_hash=token_hash,
            invited_by_user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
        )
        db.add(invite)
    else:
        action = AuditAction.organization_invite_resent.value
        invite.role = normalized_role
        invite.invite_token_hash = token_hash
        invite.invited_by_user_id = user.id
        invite.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
        invite.status = "pending"
        invite.accepted_at = None
        invite.accepted_by_user_id = None

    db.flush()
    invite_email_sent = send_organization_invite_email(
        to_email=normalized_email,
        organization_name=org.name,
        role=normalized_role,
        inviter_email=user.email,
        token=token,
    )
    if not invite_email_sent and settings.invite_email_enabled:
        logger.warning("organization invite email not sent for org_id=%s email=%s", org_id, normalized_email)
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=action,
        target_type="organization_invite",
        target_id=invite.id,
        organization_id=org_id,
        metadata={
            "email": normalized_email,
            "role": normalized_role,
            "expires_at": invite.expires_at.isoformat(),
            "invite_email_sent": invite_email_sent,
        },
    )
    db.commit()
    db.refresh(invite)
    return OrganizationInviteIssueResponse(invite=_serialize_org_invite(invite), invite_token=token)


@router.post("/{org_id}/invites/{invite_id}/resend", response_model=OrganizationInviteIssueResponse)
def resend_organization_invite(
    org_id: UUID,
    invite_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationInviteIssueResponse:
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    invite = (
        db.query(OrganizationInvite)
        .filter(OrganizationInvite.id == invite_id, OrganizationInvite.organization_id == org_id)
        .one_or_none()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending invites can be resent")

    token, token_hash = _issue_invite_token()
    invite.invite_token_hash = token_hash
    invite.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
    invite.invited_by_user_id = user.id
    db.flush()
    invite_email_sent = send_organization_invite_email(
        to_email=invite.email,
        organization_name=org.name,
        role=invite.role,
        inviter_email=user.email,
        token=token,
    )
    if not invite_email_sent and settings.invite_email_enabled:
        logger.warning("organization invite resend email not sent for org_id=%s email=%s", org_id, invite.email)
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_invite_resent.value,
        target_type="organization_invite",
        target_id=invite.id,
        organization_id=org_id,
        metadata={"email": invite.email, "role": invite.role, "invite_email_sent": invite_email_sent},
    )
    db.commit()
    db.refresh(invite)
    return OrganizationInviteIssueResponse(invite=_serialize_org_invite(invite), invite_token=token)


@router.delete("/{org_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_organization_invite(
    org_id: UUID,
    invite_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _require_org_owner(db, org_id, user)
    invite = (
        db.query(OrganizationInvite)
        .filter(OrganizationInvite.id == invite_id, OrganizationInvite.organization_id == org_id)
        .one_or_none()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending invites can be revoked")
    invite.status = "revoked"
    db.flush()
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_invite_revoked.value,
        target_type="organization_invite",
        target_id=invite.id,
        organization_id=org_id,
        metadata={"email": invite.email},
    )
    db.commit()


@router.post("/invites/accept", response_model=OrganizationMemberPublic)
@limiter.exempt
def accept_organization_invite(
    body: OrganizationInviteAcceptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationMemberPublic:
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.invite_token_hash == token_hash,
            OrganizationInvite.status == "pending",
        )
        .one_or_none()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found or already used")

    now = datetime.now(timezone.utc)
    if invite.expires_at < now:
        invite.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Invite has expired")
    if invite.email.lower() != user.email.lower():
        raise HTTPException(
            status_code=403,
            detail=f"Invite is for {invite.email}, but you are signed in as {user.email}. Sign in with the invited email and try again.",
        )

    membership = _get_org_membership(db, invite.organization_id, user.id)
    if membership is None:
        ensure_seat_available(db, invite.organization_id)
        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=invite.organization_id,
            role=invite.role,
        )
        db.add(membership)
    else:
        membership.role = invite.role
    _ensure_default_workspace_membership(db, invite.organization_id, user.id, membership.role)

    invite.status = "accepted"
    invite.accepted_by_user_id = user.id
    invite.accepted_at = now
    db.flush()
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_invite_accepted.value,
        target_type="organization_invite",
        target_id=invite.id,
        organization_id=invite.organization_id,
        metadata={"email": invite.email, "role": invite.role},
    )
    db.commit()
    db.refresh(membership)
    return _serialize_org_member(membership)


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


@router.get("/{org_id}/overview-stats", response_model=OrganizationOverviewStats)
def get_organization_overview_stats(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationOverviewStats:
    """Member and indexed document counts for org overview UI (not restricted to org_owner)."""
    _require_org_membership(db, org_id, user)
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    member_count = (
        db.query(func.count(OrganizationMembership.id))
        .filter(OrganizationMembership.organization_id == org_id)
        .scalar()
        or 0
    )
    document_count = (
        db.query(func.count(Document.id)).filter(Document.organization_id == org_id).scalar() or 0
    )
    return OrganizationOverviewStats(member_count=int(member_count), document_count=int(document_count))


@router.get("/{org_id}/documents")
def list_organization_documents(
    org_id: UUID,
    request: Request,
    workspace_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, description="Optional filename/source search"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    _require_org_owner(db, org_id, user)
    enforce_privileged_read_api_limit(request, user)
    return list_documents_for_org(
        db,
        organization_id=org_id,
        workspace_id=workspace_id,
        q=q,
        limit=limit,
    )


@router.get("/{org_id}/audit")
@limiter.exempt
def list_organization_audit(
    org_id: UUID,
    request: Request,
    action: str | None = Query(default=None),
    workspace_id: UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    membership = _get_org_membership(db, org_id, user.id)
    is_org_owner = user.is_platform_owner or (
        membership is not None and membership.role == OrgMembershipRole.org_owner.value
    )
    workspace_scope_ids: list[UUID] | None = None
    if not is_org_owner:
        workspace_scope_ids = _workspace_admin_workspace_ids_in_org(db, org_id, user.id)
        if not workspace_scope_ids:
            raise HTTPException(status_code=403, detail="Workspace admin or org owner role required")
        if workspace_id is not None and workspace_id not in workspace_scope_ids:
            raise HTTPException(status_code=403, detail="Not allowed to view audit for this workspace")
    enforce_privileged_read_api_limit(request, user)
    return list_audit_events_for_org(
        db,
        organization_id=org_id,
        action=action,
        workspace_id=workspace_id if is_org_owner else None,
        workspace_ids=workspace_scope_ids if not is_org_owner else None,
        limit=limit,
    )


@router.get("/{org_id}/members", response_model=list[OrganizationMemberPublic])
def list_organization_members(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrganizationMemberPublic]:
    _require_org_owner(db, org_id, user)
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
        ensure_seat_available(db, org_id)
        membership = OrganizationMembership(
            user_id=target_user.id,
            organization_id=org_id,
            role=normalized_role,
        )
        db.add(membership)
    else:
        membership.role = normalized_role

    _ensure_default_workspace_membership(db, org_id, target_user.id, normalized_role)

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

    patch = body.model_dump(exclude_unset=True)

    if "name" in patch and patch["name"] is not None:
        org.name = patch["name"].strip()
    if "status" in patch and patch["status"] is not None:
        normalized_status = patch["status"].strip().lower()
        allowed_statuses = {status.value for status in OrgStatus}
        if normalized_status not in allowed_statuses:
            raise HTTPException(status_code=422, detail=f"Invalid status. Allowed: {sorted(allowed_statuses)}")
        org.status = normalized_status
    if "description" in patch:
        raw_desc = patch["description"]
        org.description = (raw_desc or "").strip() or None
    if "preferred_chat_provider" in patch:
        raw = patch["preferred_chat_provider"]
        if raw is None:
            org.preferred_chat_provider = None
        else:
            s = str(raw).strip().lower()
            if s in ("", "inherit", "platform", "default"):
                org.preferred_chat_provider = None
            elif s in ("extractive", "ollama", "openai", "anthropic"):
                org.preferred_chat_provider = s
            else:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Invalid preferred_chat_provider. Use extractive, ollama, openai, anthropic, "
                        "or null for platform default."
                    ),
                )
    if "preferred_chat_model" in patch:
        raw_m = patch["preferred_chat_model"]
        org.preferred_chat_model = (raw_m or "").strip() or None

    if "openai_api_key" in patch:
        raw_key = patch["openai_api_key"]
        if raw_key is None or (isinstance(raw_key, str) and not str(raw_key).strip()):
            org.openai_api_key_encrypted = None
        else:
            try:
                org.openai_api_key_encrypted = encrypt_org_secret(str(raw_key))
            except RuntimeError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Server is not configured to store organization API keys (set ORG_LLM_FERNET_KEY).",
                ) from None
    if "anthropic_api_key" in patch:
        raw_key = patch["anthropic_api_key"]
        if raw_key is None or (isinstance(raw_key, str) and not str(raw_key).strip()):
            org.anthropic_api_key_encrypted = None
        else:
            try:
                org.anthropic_api_key_encrypted = encrypt_org_secret(str(raw_key))
            except RuntimeError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Server is not configured to store organization API keys (set ORG_LLM_FERNET_KEY).",
                ) from None
    if "cohere_api_key" in patch:
        raw_key = patch["cohere_api_key"]
        if raw_key is None or (isinstance(raw_key, str) and not str(raw_key).strip()):
            org.cohere_api_key_encrypted = None
        else:
            try:
                org.cohere_api_key_encrypted = encrypt_org_secret(str(raw_key))
            except RuntimeError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Server is not configured to store organization API keys (set ORG_LLM_FERNET_KEY).",
                ) from None
    if "openai_api_base_url" in patch:
        raw_u = patch["openai_api_base_url"]
        org.openai_api_base_url = None if raw_u is None else (str(raw_u).strip() or None)
    if "anthropic_api_base_url" in patch:
        raw_u = patch["anthropic_api_base_url"]
        org.anthropic_api_base_url = None if raw_u is None else (str(raw_u).strip() or None)
    if "ollama_base_url" in patch:
        raw_u = patch["ollama_base_url"]
        org.ollama_base_url = None if raw_u is None else (str(raw_u).strip() or None)
    if "retrieval_strategy" in patch:
        raw_rs = patch["retrieval_strategy"]
        if raw_rs is None:
            org.retrieval_strategy = None
        else:
            s = str(raw_rs).strip().lower()
            if s in ("", "inherit", "platform", "default"):
                org.retrieval_strategy = None
            elif s in ("heuristic", "hybrid", "rerank"):
                org.retrieval_strategy = s
            else:
                raise HTTPException(
                    status_code=422,
                    detail="Invalid retrieval_strategy. Use heuristic, hybrid, rerank, or null for platform default.",
                )
    if "use_hosted_rerank" in patch:
        raw_ur = patch["use_hosted_rerank"]
        org.use_hosted_rerank = bool(raw_ur) if raw_ur is not None else False
    if "allowed_connector_ids" in patch:
        normalized_allowed = _normalize_allowed_connector_ids(patch["allowed_connector_ids"])
        connectors_max = int(get_plan_entitlements(org.plan).connectors)
        catalog_size = len(settings.connector_catalog())
        if normalized_allowed is None and catalog_size > connectors_max:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Plan connector limit is {connectors_max}. "
                    "Select up to that many connectors for this organization."
                ),
            )
        if normalized_allowed is not None and len(normalized_allowed) > connectors_max:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Plan connector limit is {connectors_max}. "
                    f"You selected {len(normalized_allowed)}."
                ),
            )
        org.allowed_connector_ids = normalized_allowed

    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_updated.value,
        target_type="organization",
        target_id=org.id,
        organization_id=org.id,
        metadata={
            "name": org.name,
            "status": org.status,
            "has_description": org.description is not None,
            "preferred_chat_provider": org.preferred_chat_provider,
            "allowed_connector_count": len(org.allowed_connector_ids or []),
        },
    )
    db.commit()
    db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization_endpoint(
    org_id: UUID,
    confirm_slug: str = Query(
        ...,
        min_length=1,
        description="Must match the organization URL slug (case-insensitive). Deletes all workspaces, documents, chats, and connectors under this org.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Org owners and platform owners. Removes stored PDF files, then deletes the org row (DB CASCADE for related data)."""
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if confirm_slug.strip().lower() != org.slug.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="confirm_slug must match the organization slug",
        )
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.organization_deleted.value,
        target_type="organization",
        target_id=org.id,
        organization_id=org.id,
        metadata={"name": org.name, "slug": org.slug},
    )
    delete_organization_cascade(db, org.id)
    db.commit()


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
    if user.is_platform_owner:
        rows = db.query(Workspace).order_by(Workspace.created_at.asc()).all()
        return list(rows)
    rows = (
        db.query(Workspace)
        .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .outerjoin(
            OrganizationMembership,
            OrganizationMembership.organization_id == Workspace.organization_id,
        )
        .filter(
            (WorkspaceMember.user_id == user.id)
            | (
                (OrganizationMembership.user_id == user.id)
                & (OrganizationMembership.role == OrgMembershipRole.org_owner.value)
            )
        )
        .distinct()
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
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    return workspace


@router_w.get("/{workspace_id}/members", response_model=list[WorkspaceMemberPublic])
def list_workspace_members(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkspaceMemberPublic]:
    workspace = _require_workspace_admin(db, workspace_id, user)

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
    _require_org_membership(db, workspace.organization_id, target_user, allow_platform_owner_bypass=False)
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


@router_w.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_endpoint(
    workspace_id: UUID,
    confirm_name: str = Query(
        ...,
        min_length=1,
        description="Must match the workspace name exactly (trimmed). Removes indexed documents, chats, and stored files for this workspace.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    _require_org_owner(db, workspace.organization_id, user)
    if confirm_name.strip() != workspace.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="confirm_name must match the workspace name exactly",
        )
    n_ws = (
        db.query(Workspace)
        .filter(Workspace.organization_id == workspace.organization_id)
        .count()
    )
    if n_ws <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last workspace in this organization",
        )
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.workspace_deleted.value,
        target_type="workspace",
        target_id=workspace.id,
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        metadata={"name": workspace.name},
    )
    delete_workspace_cascade(db, workspace_id)
    db.commit()


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
