"""
Optional demo org + workspace for a seeded platform owner (local / pilot).

Requires DATABASE_URL and an existing user matching SEED_PLATFORM_OWNER_EMAIL.
Defaults match the law-firm sample org (Sterling & Vale LLP). Set SEED_DEMO_WORKSPACE=true
to run (idempotent: reuses existing org slug and ensures the pilot workspace exists).

Usage:
  SEED_DEMO_WORKSPACE=true python scripts/seed_demo_workspace.py
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


def _ensure_org_owner_membership(db, *, user_id, org_id) -> None:
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
        db.add(
            OrganizationMembership(
                user_id=user_id,
                organization_id=org_id,
                role=OrgMembershipRole.org_owner.value,
            )
        )
    elif m.role != OrgMembershipRole.org_owner.value:
        m.role = OrgMembershipRole.org_owner.value
        db.add(m)


def _ensure_workspace_admin(db, *, user_id, workspace_id) -> None:
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
        db.add(
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                role=WorkspaceMemberRole.workspace_admin.value,
            )
        )
    elif m.role != WorkspaceMemberRole.workspace_admin.value:
        m.role = WorkspaceMemberRole.workspace_admin.value
        db.add(m)


def main() -> None:
    if os.environ.get("SEED_DEMO_WORKSPACE", "").lower() not in ("1", "true", "yes"):
        print("Set SEED_DEMO_WORKSPACE=true to run this script.")
        return

    email = os.environ.get("SEED_PLATFORM_OWNER_EMAIL", "owner@example.com").lower().strip()
    org_name = os.environ.get("DEMO_ORG_NAME", "Sterling & Vale LLP")
    org_slug = os.environ.get("DEMO_ORG_SLUG", "sterling-vale-llp").strip().lower()
    ws_name = os.environ.get("DEMO_WORKSPACE_NAME", "Pilot Workspace")

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            print(f"No user found for {email}; run scripts/seed.py first.")
            sys.exit(1)

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

        _ensure_org_owner_membership(db, user_id=user.id, org_id=org.id)

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
                description="Seeded demo workspace for PDF upload and chat.",
                created_by=user.id,
            )
            db.add(ws)
            db.flush()

        _ensure_workspace_admin(db, user_id=user.id, workspace_id=ws.id)
        db.commit()
        print(f"Ensured org {org.slug} and workspace {ws.name} ({ws.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
