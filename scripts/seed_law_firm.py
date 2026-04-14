"""
Seed a rich sample law-firm organization for the platform owner (demo / UX testing).

Creates (idempotent — skips if the organization slug already exists):
  - Organization: Sterling & Vale LLP (business plan, demo Stripe ids)
  - Multiple practice workspaces + General
  - Platform owner as org_owner + workspace_admin on each workspace
  - Optional second user (associate) for Team UI
  - Pending org invites (partner / summer programs)
  - OrganizationConnector + IntegrationConnector rows (healthy / synced demo state)
  - Chat sessions, query logs, audit events

Requires DATABASE_URL and an existing user matching SEED_PLATFORM_OWNER_EMAIL
(same as scripts/seed.py).

Usage:
  SEED_LAW_FIRM=true python scripts/seed_law_firm.py

Docker:
  docker compose -f docker-compose.gpu.yml exec -e SEED_LAW_FIRM=true api python scripts/seed_law_firm.py
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
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
    AuditAction,
    AuditLog,
    ChatSession,
    IntegrationConnector,
    Organization,
    OrganizationConnector,
    OrganizationInvite,
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    QueryLog,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    utcnow,
)


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _issue_invite_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, token_hash


WORKSPACES: list[tuple[str, str, str]] = [
    (
        "General",
        "Firm-wide coordination, announcements, and shared administrative knowledge.",
        "Firm operations",
    ),
    (
        "Litigation & Disputes",
        "Active matters, pleadings, discovery, expert materials, and court deadlines.",
        "Case strategy",
    ),
    (
        "Corporate & Transactions",
        "M&A, commercial contracts, entity work, and vendor / customer diligence.",
        "Deals pipeline",
    ),
    (
        "Knowledge & Precedents",
        "Clause banks, research memos, practice notes, and reusable templates.",
        "Research",
    ),
    (
        "Client Intake & Conflicts",
        "New business screening, conflict checks, engagement letters, and CRM handoff.",
        "Intake",
    ),
]

# Frontend connector ids (see HomePage CONNECTORS catalogue)
SEED_CONNECTORS: list[tuple[str, str, int]] = [
    ("sharepoint", "nango_seed_sharepoint_svllp", 1840),
    ("confluence", "nango_seed_confluence_svllp", 620),
    ("google-drive", "nango_seed_gdrive_svllp", 430),
]

PENDING_INVITES: list[tuple[str, str]] = [
    ("partner.candidate@external-firm.example", OrgMembershipRole.org_owner.value),
    ("summer.associate@law-school.example", OrgMembershipRole.member.value),
]


def main() -> None:
    if not _truthy(os.environ.get("SEED_LAW_FIRM")):
        print("Set SEED_LAW_FIRM=true to run this script.")
        return

    owner_email = os.environ.get("SEED_PLATFORM_OWNER_EMAIL", "owner@example.com").lower().strip()
    org_name = os.environ.get("LAW_FIRM_ORG_NAME", "Sterling & Vale LLP")
    org_slug = os.environ.get("LAW_FIRM_ORG_SLUG", "sterling-vale-llp").strip().lower()

    associate_email = os.environ.get("LAW_FIRM_ASSOCIATE_EMAIL", "morgan.lee@sterlingvale.demo").lower().strip()
    associate_password = os.environ.get("LAW_FIRM_ASSOCIATE_PASSWORD", "DemoLaw2026!")
    associate_name = os.environ.get("LAW_FIRM_ASSOCIATE_NAME", "Morgan Lee")

    db = SessionLocal()
    try:
        owner = db.execute(select(User).where(User.email == owner_email)).scalar_one_or_none()
        if owner is None:
            print(f"No user found for {owner_email}; run scripts/seed.py first.")
            sys.exit(1)
        if not owner.is_platform_owner:
            print(f"User {owner_email} is not a platform owner; promote or use SEED_PLATFORM_OWNER_EMAIL.")
            sys.exit(1)

        existing_org = db.execute(select(Organization).where(Organization.slug == org_slug)).scalar_one_or_none()
        if existing_org is not None:
            print(f"Law firm sample already present (slug={org_slug}, id={existing_org.id}). Skipping.")
            return

        org = Organization(
            name=org_name,
            slug=org_slug,
            tenant_key=secrets.token_urlsafe(16),
            status=OrgStatus.active.value,
            plan="business",
            stripe_customer_id="cus_seed_sterling_vale_demo",
            stripe_subscription_id="sub_seed_sterling_vale_demo",
            billing_grace_until=None,
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

        now = utcnow()
        ws_map: dict[str, Workspace] = {}
        for name, description, _chat_hint in WORKSPACES:
            ws = Workspace(
                organization_id=org.id,
                name=name,
                description=description,
                created_by=owner.id,
            )
            db.add(ws)
            db.flush()
            ws_map[name] = ws
            db.add(
                WorkspaceMember(
                    workspace_id=ws.id,
                    user_id=owner.id,
                    role=WorkspaceMemberRole.workspace_admin.value,
                )
            )
            db.add(
                ChatSession(
                    organization_id=org.id,
                    workspace_id=ws.id,
                    user_id=owner.id,
                    title=_chat_hint,
                )
            )
            db.add(
                AuditLog(
                    actor_user_id=owner.id,
                    organization_id=org.id,
                    workspace_id=ws.id,
                    action=AuditAction.workspace_created.value,
                    target_type="workspace",
                    target_id=ws.id,
                    metadata_json={"name": name, "seed": "law_firm"},
                )
            )

        # Demo connectors (catalogue + Nango-style rows)
        default_ws = ws_map["Knowledge & Precedents"]
        for integration_key, nango_id, doc_count in SEED_CONNECTORS:
            db.add(
                OrganizationConnector(
                    organization_id=org.id,
                    integration_key=integration_key,
                )
            )
            db.add(
                IntegrationConnector(
                    organization_id=org.id,
                    connector_type=integration_key,
                    nango_connection_id=nango_id,
                    status="active",
                    last_synced_at=now - timedelta(hours=2),
                    document_count=doc_count,
                    config={
                        "workspace_id": str(default_ws.id),
                        "sync_scope": "full",
                        "seed": True,
                    },
                )
            )

        # Pending invites (tokens are discarded after hash; UI shows pending list)
        for email, role in PENDING_INVITES:
            _, token_hash = _issue_invite_token()
            db.add(
                OrganizationInvite(
                    organization_id=org.id,
                    email=email.lower().strip(),
                    role=role,
                    status="pending",
                    invite_token_hash=token_hash,
                    invited_by_user_id=owner.id,
                    expires_at=now + timedelta(days=14),
                )
            )
            db.add(
                AuditLog(
                    actor_user_id=owner.id,
                    organization_id=org.id,
                    action=AuditAction.organization_invite_sent.value,
                    target_type="organization_invite",
                    target_id=None,
                    metadata_json={"email": email, "role": role, "seed": "law_firm"},
                )
            )

        # Optional associate user — populates Team management UI
        assoc = db.execute(select(User).where(User.email == associate_email)).scalar_one_or_none()
        if assoc is None:
            assoc = User(
                email=associate_email,
                password_hash=hash_password(associate_password),
                full_name=associate_name,
                is_active=True,
                is_platform_owner=False,
            )
            db.add(assoc)
            db.flush()
        db.add(
            OrganizationMembership(
                user_id=assoc.id,
                organization_id=org.id,
                role=OrgMembershipRole.member.value,
            )
        )
        for name, _desc, _hint in WORKSPACES:
            ws = ws_map[name]
            db.add(
                WorkspaceMember(
                    workspace_id=ws.id,
                    user_id=assoc.id,
                    role=WorkspaceMemberRole.member.value,
                )
            )

        # Sample analytics / RAG audit trail
        lit = ws_map["Litigation & Disputes"]
        corp = ws_map["Corporate & Transactions"]
        db.add(
            QueryLog(
                organization_id=org.id,
                workspace_id=lit.id,
                user_id=owner.id,
                question="Summarize our standard motion to dismiss checklist for federal court.",
                answer=(
                    "Key steps: (1) verify subject-matter jurisdiction, (2) check statute of limitations, "
                    "(3) map elements to pleaded facts, (4) attach controlling authority from the Knowledge workspace."
                ),
                citations_json=[{"label": "Playbook / MTD checklist", "document_id": None}],
                confidence="high",
                duration_ms=840,
                token_count=420,
                feedback=None,
            )
        )
        db.add(
            QueryLog(
                organization_id=org.id,
                workspace_id=corp.id,
                user_id=owner.id,
                question="What indemnity carve-outs did we use in the last three vendor MSAs?",
                answer=(
                    "Typical carve-outs: gross negligence, willful misconduct, IP indemnity caps, "
                    "and exclusions for matters disclosed on schedules (see Knowledge & Precedents templates)."
                ),
                citations_json=[],
                confidence="medium",
                duration_ms=1205,
                token_count=310,
                feedback="helpful",
            )
        )

        db.add(
            AuditLog(
                actor_user_id=owner.id,
                organization_id=org.id,
                action=AuditAction.organization_created.value,
                target_type="organization",
                target_id=org.id,
                metadata_json={"slug": org.slug, "plan": org.plan, "seed": "law_firm"},
            )
        )

        db.commit()
        print(f"Seeded law firm organization: {org.name} ({org.slug})")
        print(f"  Organization id: {org.id}")
        print(f"  Workspaces: {len(ws_map)}")
        print(f"  Associate login: {associate_email} / {associate_password}")
        print("  Platform owner retains org_owner and full workspace admin access.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
