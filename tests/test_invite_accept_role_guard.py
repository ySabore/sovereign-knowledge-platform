"""Stale invite accept must not demote an elevated membership (org lockout)."""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models import (
    Organization,
    OrganizationInvite,
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.routers.organizations import DEFAULT_WORKSPACE_NAME


class InviteAcceptRoleGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        app = create_app()

        def override_get_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._seed()

    def _seed(self) -> None:
        db = self.SessionLocal()
        try:
            self.owner = User(
                email="alice-owner@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Alice Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.invitee = User(
                email="bob-invitee@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Bob Invitee",
                is_active=True,
                is_platform_owner=False,
            )
            db.add_all([self.owner, self.invitee])
            db.flush()

            org = Organization(
                name="Handoff Org",
                slug=f"handoff-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
                plan="team",
            )
            db.add(org)
            db.flush()
            self.org_id = org.id
            self.owner_id = self.owner.id
            self.invitee_id = self.invitee.id

            general = Workspace(
                organization_id=org.id,
                name=DEFAULT_WORKSPACE_NAME,
                description="Default workspace",
            )
            db.add(general)
            db.flush()
            self.workspace_id = general.id

            db.add_all(
                [
                    OrganizationMembership(
                        user_id=self.owner.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.org_owner.value,
                    ),
                    WorkspaceMember(
                        user_id=self.owner.id,
                        workspace_id=general.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

    def _login(self, email: str, password: str = "ChangeMeNow!") -> dict[str, str]:
        resp = self.client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(resp.status_code, 200, resp.text)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def _invite_bob_as_member(self) -> str:
        headers = self._login("alice-owner@example.com")
        resp = self.client.post(
            f"/organizations/{self.org_id}/invites",
            headers=headers,
            json={"email": "bob-invitee@example.com", "role": "member"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        token = resp.json()["invite_token"]
        self.assertTrue(token)
        return token

    def _owner_count(self) -> int:
        db = self.SessionLocal()
        try:
            return (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == self.org_id,
                    OrganizationMembership.role == OrgMembershipRole.org_owner.value,
                )
                .count()
            )
        finally:
            db.close()

    def _bob_org_role(self) -> str | None:
        db = self.SessionLocal()
        try:
            row = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == self.org_id,
                    OrganizationMembership.user_id == self.invitee_id,
                )
                .one_or_none()
            )
            return None if row is None else row.role
        finally:
            db.close()

    def test_new_invitee_still_receives_invited_role(self) -> None:
        token = self._invite_bob_as_member()
        headers = self._login("bob-invitee@example.com")
        resp = self.client.post("/organizations/invites/accept", headers=headers, json={"token": token})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["role"], "member")
        self.assertEqual(self._bob_org_role(), "member")
        self.assertEqual(self._owner_count(), 1)

    def test_stale_member_invite_does_not_demote_last_org_owner(self) -> None:
        """Invite as member, promote via PUT, founding owner leaves, invitee clicks old link."""
        token = self._invite_bob_as_member()
        owner_headers = self._login("alice-owner@example.com")

        upsert = self.client.put(
            f"/organizations/{self.org_id}/members",
            headers=owner_headers,
            json={"email": "bob-invitee@example.com", "role": "org_owner"},
        )
        self.assertEqual(upsert.status_code, 200, upsert.text)
        self.assertEqual(self._bob_org_role(), "org_owner")
        self.assertEqual(self._owner_count(), 2)

        remove = self.client.delete(
            f"/organizations/{self.org_id}/members/{self.owner_id}",
            headers=owner_headers,
        )
        self.assertEqual(remove.status_code, 204, remove.text)
        self.assertEqual(self._owner_count(), 1)

        bob_headers = self._login("bob-invitee@example.com")
        accept = self.client.post(
            "/organizations/invites/accept",
            headers=bob_headers,
            json={"token": token},
        )
        # Upsert revokes the pending invite; the stale email link must not apply.
        self.assertEqual(accept.status_code, 404, accept.text)
        self.assertEqual(self._bob_org_role(), "org_owner")
        self.assertEqual(self._owner_count(), 1)

    def test_accept_keeps_elevated_role_if_invite_still_pending(self) -> None:
        """Defense in depth: even a still-pending member invite cannot clobber org_owner."""
        owner_headers = self._login("alice-owner@example.com")
        invite = self.client.post(
            f"/organizations/{self.org_id}/invites",
            headers=owner_headers,
            json={"email": "bob-invitee@example.com", "role": "member"},
        )
        self.assertEqual(invite.status_code, 201, invite.text)
        token = invite.json()["invite_token"]

        # Simulate a membership granted outside the invite consume path, without
        # going through PUT (which now revokes pending invites).
        db = self.SessionLocal()
        try:
            db.add(
                OrganizationMembership(
                    user_id=self.invitee_id,
                    organization_id=self.org_id,
                    role=OrgMembershipRole.org_owner.value,
                )
            )
            db.add(
                WorkspaceMember(
                    user_id=self.invitee_id,
                    workspace_id=self.workspace_id,
                    role=WorkspaceMemberRole.workspace_admin.value,
                )
            )
            db.query(OrganizationMembership).filter(
                OrganizationMembership.user_id == self.owner_id,
                OrganizationMembership.organization_id == self.org_id,
            ).delete()
            db.commit()
        finally:
            db.close()
        self.assertEqual(self._owner_count(), 1)

        bob_headers = self._login("bob-invitee@example.com")
        accept = self.client.post(
            "/organizations/invites/accept",
            headers=bob_headers,
            json={"token": token},
        )
        self.assertEqual(accept.status_code, 200, accept.text)
        self.assertEqual(accept.json()["role"], "org_owner")
        self.assertEqual(self._bob_org_role(), "org_owner")
        self.assertEqual(self._owner_count(), 1)

        db = self.SessionLocal()
        try:
            ws = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == self.workspace_id,
                    WorkspaceMember.user_id == self.invitee_id,
                )
                .one()
            )
            self.assertEqual(ws.role, WorkspaceMemberRole.workspace_admin.value)
            inv = db.query(OrganizationInvite).filter(OrganizationInvite.email == "bob-invitee@example.com").one()
            self.assertEqual(inv.status, "accepted")
        finally:
            db.close()

    def test_member_upsert_revokes_pending_invite_for_same_email(self) -> None:
        token = self._invite_bob_as_member()
        owner_headers = self._login("alice-owner@example.com")
        upsert = self.client.put(
            f"/organizations/{self.org_id}/members",
            headers=owner_headers,
            json={"email": "bob-invitee@example.com", "role": "member"},
        )
        self.assertEqual(upsert.status_code, 200, upsert.text)

        db = self.SessionLocal()
        try:
            inv = db.query(OrganizationInvite).filter(OrganizationInvite.email == "bob-invitee@example.com").one()
            self.assertEqual(inv.status, "revoked")
        finally:
            db.close()

        bob_headers = self._login("bob-invitee@example.com")
        accept = self.client.post(
            "/organizations/invites/accept",
            headers=bob_headers,
            json={"token": token},
        )
        self.assertEqual(accept.status_code, 404, accept.text)
        self.assertEqual(self._bob_org_role(), "member")
