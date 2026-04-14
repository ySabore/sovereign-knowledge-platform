"""
Seed demo users + org/workspace roles for local development.

Creates (idempotently):
- An organization (by slug) and a workspace (by name)
- Four users with passwords
- Organization memberships (org_owner/member)
- Workspace memberships (workspace_admin/member)

Usage (PowerShell):
  $env:SEED_DEMO_USERS="true"
  python scripts/seed_demo_users.py

Optional overrides:
  SEED_DEMO_USERS=true
  DEMO_ORG_NAME="Sterling & Vale LLP"
  DEMO_ORG_SLUG="sterling-vale-llp"
  DEMO_WORKSPACE_NAME="Pilot Workspace"

  ORG_ADMIN_EMAIL="org-admin@example.com"
  ORG_ADMIN_PASSWORD="ChangeMeNow!"
  WORKSPACE_ADMIN_EMAIL="ws-admin@example.com"
  WORKSPACE_ADMIN_PASSWORD="ChangeMeNow!"
  ORG_MEMBER_EMAIL="org-member@example.com"
  ORG_MEMBER_PASSWORD="ChangeMeNow!"
  WORKSPACE_MEMBER_EMAIL="ws-member@example.com"
  WORKSPACE_MEMBER_PASSWORD="ChangeMeNow!"

Safety:
  RESET_DEMO_PASSWORDS=true  # re-hash and reset passwords if users already exist
"""

from __future__ import annotations

import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import SessionLocal
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


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _get_or_create_user(
    *,
    db,
    email: str,
    password: str,
    full_name: str,
    reset_passwords: bool,
) -> User:
    email_norm = email.lower().strip()
    u = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if u is None:
        u = User(
            email=email_norm,
            password_hash=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_platform_owner=False,
        )
        db.add(u)
        db.flush()
        return u
    if reset_passwords:
        u.password_hash = hash_password(password)
        db.add(u)
    return u


def _upsert_org_membership(*, db, user_id, org_id, role: str) -> None:
    m = (
        db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == org_id,
            )
        )
        .scalar_one_or_none()
    )
    if m is None:
        db.add(OrganizationMembership(user_id=user_id, organization_id=org_id, role=role))
    else:
        m.role = role
        db.add(m)


def _upsert_workspace_membership(*, db, user_id, workspace_id, role: str) -> None:
    m = (
        db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
        )
        .scalar_one_or_none()
    )
    if m is None:
        db.add(WorkspaceMember(user_id=user_id, workspace_id=workspace_id, role=role))
    else:
        m.role = role
        db.add(m)


def main() -> None:
    if not _truthy(os.environ.get("SEED_DEMO_USERS")):
        print("Set SEED_DEMO_USERS=true to run this script.")
        return

    reset_passwords = _truthy(os.environ.get("RESET_DEMO_PASSWORDS"))

    org_name = os.environ.get("DEMO_ORG_NAME", "Sterling & Vale LLP").strip()
    org_slug = os.environ.get("DEMO_ORG_SLUG", "sterling-vale-llp").strip().lower()
    ws_name = os.environ.get("DEMO_WORKSPACE_NAME", "Pilot Workspace").strip()

    creds = {
        "org_admin": {
            "email": os.environ.get("ORG_ADMIN_EMAIL", "org-admin@example.com"),
            "password": os.environ.get("ORG_ADMIN_PASSWORD", "ChangeMeNow!"),
            "full_name": os.environ.get("ORG_ADMIN_NAME", "Org Admin"),
        },
        "workspace_admin": {
            "email": os.environ.get("WORKSPACE_ADMIN_EMAIL", "ws-admin@example.com"),
            "password": os.environ.get("WORKSPACE_ADMIN_PASSWORD", "ChangeMeNow!"),
            "full_name": os.environ.get("WORKSPACE_ADMIN_NAME", "Workspace Admin"),
        },
        "org_member": {
            "email": os.environ.get("ORG_MEMBER_EMAIL", "org-member@example.com"),
            "password": os.environ.get("ORG_MEMBER_PASSWORD", "ChangeMeNow!"),
            "full_name": os.environ.get("ORG_MEMBER_NAME", "Org Member"),
        },
        "workspace_member": {
            "email": os.environ.get("WORKSPACE_MEMBER_EMAIL", "ws-member@example.com"),
            "password": os.environ.get("WORKSPACE_MEMBER_PASSWORD", "ChangeMeNow!"),
            "full_name": os.environ.get("WORKSPACE_MEMBER_NAME", "Workspace Member"),
        },
    }

    db = SessionLocal()
    try:
        org = db.execute(select(Organization).where(Organization.slug == org_slug)).scalar_one_or_none()
        if org is None:
            org = Organization(
                name=org_name,
                slug=org_slug,
                tenant_key=secrets.token_urlsafe(16),
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()

        ws = (
            db.execute(
                select(Workspace).where(
                    Workspace.organization_id == org.id,
                    Workspace.name == ws_name,
                )
            )
            .scalar_one_or_none()
        )
        if ws is None:
            ws = Workspace(
                organization_id=org.id,
                name=ws_name,
                description="Seeded demo workspace for uploads and chat.",
            )
            db.add(ws)
            db.flush()

        # Users
        u_org_admin = _get_or_create_user(db=db, reset_passwords=reset_passwords, **creds["org_admin"])
        u_ws_admin = _get_or_create_user(db=db, reset_passwords=reset_passwords, **creds["workspace_admin"])
        u_org_member = _get_or_create_user(db=db, reset_passwords=reset_passwords, **creds["org_member"])
        u_ws_member = _get_or_create_user(db=db, reset_passwords=reset_passwords, **creds["workspace_member"])

        # Org memberships
        _upsert_org_membership(db=db, user_id=u_org_admin.id, org_id=org.id, role=OrgMembershipRole.org_owner.value)
        _upsert_org_membership(db=db, user_id=u_ws_admin.id, org_id=org.id, role=OrgMembershipRole.member.value)
        _upsert_org_membership(db=db, user_id=u_org_member.id, org_id=org.id, role=OrgMembershipRole.member.value)
        _upsert_org_membership(db=db, user_id=u_ws_member.id, org_id=org.id, role=OrgMembershipRole.member.value)

        # Workspace memberships
        _upsert_workspace_membership(db=db, user_id=u_org_admin.id, workspace_id=ws.id, role=WorkspaceMemberRole.workspace_admin.value)
        _upsert_workspace_membership(db=db, user_id=u_ws_admin.id, workspace_id=ws.id, role=WorkspaceMemberRole.workspace_admin.value)
        _upsert_workspace_membership(db=db, user_id=u_org_member.id, workspace_id=ws.id, role=WorkspaceMemberRole.member.value)
        _upsert_workspace_membership(db=db, user_id=u_ws_member.id, workspace_id=ws.id, role=WorkspaceMemberRole.member.value)

        db.commit()

        print("")
        print("Seeded demo accounts (use /auth/login):")
        for k in ("org_admin", "workspace_admin", "org_member", "workspace_member"):
            print(f"- {k}: {creds[k]['email']} / {creds[k]['password']}")
        print("")
        print(f"Org: {org.slug}")
        print(f"Workspace: {ws.name} ({ws.id})")
        if reset_passwords:
            print("NOTE: RESET_DEMO_PASSWORDS=true was set (passwords were reset if users existed).")
    finally:
        db.close()


if __name__ == "__main__":
    main()

