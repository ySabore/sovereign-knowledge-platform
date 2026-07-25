"""Critical authz: org removal, invite demotion, chat upload contributor, full-RBAC docs."""

from __future__ import annotations

import hashlib
import os
import unittest
from datetime import datetime, timedelta
from io import BytesIO
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.config import settings
from app.database import Base, get_db
from app.main import create_app
from app.models import (
    Document,
    DocumentPermission,
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


class OrgMembershipRevocationTests(unittest.TestCase):
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
        self._prev_rbac = settings.rbac_mode
        settings.rbac_mode = "simple"
        self._seed()

    def tearDown(self) -> None:
        settings.rbac_mode = self._prev_rbac

    def _seed(self) -> None:
        db = self.SessionLocal()
        try:
            self.owner = User(
                email="owner-revoke@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.member = User(
                email="member-revoke@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Member",
                is_active=True,
                is_platform_owner=False,
            )
            db.add_all([self.owner, self.member])
            db.flush()
            self.owner_id = self.owner.id
            self.member_id = self.member.id
            self.owner_email = self.owner.email
            self.member_email = self.member.email

            org = Organization(
                name="Revoke Org",
                slug=f"revoke-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            self.org_id = org.id

            ws = Workspace(organization_id=org.id, name="General", description="Default")
            db.add(ws)
            db.flush()
            self.workspace_id = ws.id

            db.add_all(
                [
                    OrganizationMembership(
                        user_id=self.owner_id,
                        organization_id=org.id,
                        role=OrgMembershipRole.org_owner.value,
                    ),
                    OrganizationMembership(
                        user_id=self.member_id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    WorkspaceMember(
                        user_id=self.owner_id,
                        workspace_id=ws.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                    WorkspaceMember(
                        user_id=self.member_id,
                        workspace_id=ws.id,
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

    def test_remove_org_member_revokes_workspace_access(self) -> None:
        member_headers = self._login(self.member_email)
        before = self.client.get(f"/workspaces/{self.workspace_id}", headers=member_headers)
        self.assertEqual(before.status_code, 200, before.text)

        owner_headers = self._login(self.owner_email)
        removed = self.client.delete(
            f"/organizations/{self.org_id}/members/{self.member_id}",
            headers=owner_headers,
        )
        self.assertEqual(removed.status_code, 204, removed.text)

        after = self.client.get(f"/workspaces/{self.workspace_id}", headers=member_headers)
        self.assertEqual(after.status_code, 403, after.text)

        listed = self.client.get("/workspaces/me", headers=member_headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json(), [])

        db = self.SessionLocal()
        try:
            leftover = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.user_id == self.member_id,
                    WorkspaceMember.workspace_id == self.workspace_id,
                )
                .one_or_none()
            )
            self.assertIsNone(leftover)
        finally:
            db.close()

    def test_invite_accept_does_not_demote_existing_org_owner(self) -> None:
        db = self.SessionLocal()
        try:
            token = "stale-member-invite-token"
            invite = OrganizationInvite(
                organization_id=self.org_id,
                email=self.member_email,
                role=OrgMembershipRole.member.value,
                status="pending",
                invite_token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                invited_by_user_id=self.owner_id,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.add(invite)
            membership = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == self.org_id,
                    OrganizationMembership.user_id == self.member_id,
                )
                .one()
            )
            membership.role = OrgMembershipRole.org_owner.value
            ws_membership = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == self.workspace_id,
                    WorkspaceMember.user_id == self.member_id,
                )
                .one()
            )
            ws_membership.role = WorkspaceMemberRole.workspace_admin.value
            db.commit()
        finally:
            db.close()

        headers = self._login(self.member_email)
        resp = self.client.post("/organizations/invites/accept", json={"token": token}, headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["role"], OrgMembershipRole.org_owner.value)

        db = self.SessionLocal()
        try:
            membership = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == self.org_id,
                    OrganizationMembership.user_id == self.member_id,
                )
                .one()
            )
            self.assertEqual(membership.role, OrgMembershipRole.org_owner.value)
            ws_membership = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == self.workspace_id,
                    WorkspaceMember.user_id == self.member_id,
                )
                .one()
            )
            self.assertEqual(ws_membership.role, WorkspaceMemberRole.workspace_admin.value)
        finally:
            db.close()

    def test_upsert_member_revokes_pending_invite(self) -> None:
        db = self.SessionLocal()
        try:
            invite = OrganizationInvite(
                organization_id=self.org_id,
                email=self.member_email,
                role=OrgMembershipRole.member.value,
                status="pending",
                invite_token_hash=hashlib.sha256(b"pending").hexdigest(),
                invited_by_user_id=self.owner_id,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.add(invite)
            db.commit()
            invite_id = invite.id
        finally:
            db.close()

        owner_headers = self._login(self.owner_email)
        resp = self.client.put(
            f"/organizations/{self.org_id}/members",
            json={"email": self.member_email, "role": "org_owner"},
            headers=owner_headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        db = self.SessionLocal()
        try:
            invite = db.get(OrganizationInvite, invite_id)
            self.assertIsNotNone(invite)
            self.assertEqual(invite.status, "revoked")
        finally:
            db.close()

    def test_chat_upload_requires_contributor_role(self) -> None:
        db = self.SessionLocal()
        try:
            ws_membership = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == self.workspace_id,
                    WorkspaceMember.user_id == self.member_id,
                )
                .one()
            )
            ws_membership.role = WorkspaceMemberRole.member.value
            db.commit()
        finally:
            db.close()

        headers = self._login(self.member_email)
        resp = self.client.post(
            f"/chat/workspaces/{self.workspace_id}/upload",
            headers=headers,
            files={"file": ("note.txt", BytesIO(b"hello world"), "text/plain")},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertIn("contributor", resp.text.lower())

    def test_full_rbac_document_list_and_get_respect_permissions(self) -> None:
        settings.rbac_mode = "full"
        db = self.SessionLocal()
        try:
            allowed = Document(
                organization_id=self.org_id,
                workspace_id=self.workspace_id,
                created_by=self.owner_id,
                filename="allowed.txt",
                content_type="text/plain",
                storage_path="",
                source_type="file-upload",
                external_id=str(uuid4()),
                status="indexed",
                page_count=1,
            )
            denied = Document(
                organization_id=self.org_id,
                workspace_id=self.workspace_id,
                created_by=self.owner_id,
                filename="secret.txt",
                content_type="text/plain",
                storage_path="",
                source_type="file-upload",
                external_id=str(uuid4()),
                status="indexed",
                page_count=1,
            )
            db.add_all([allowed, denied])
            db.flush()
            db.add(
                DocumentPermission(
                    document_id=allowed.id,
                    organization_id=self.org_id,
                    user_id=self.member_id,
                    can_read=True,
                    source="test",
                    external_id="perm-1",
                )
            )
            # Member is a normal workspace member, not org owner.
            ws_membership = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == self.workspace_id,
                    WorkspaceMember.user_id == self.member_id,
                )
                .one()
            )
            ws_membership.role = WorkspaceMemberRole.member.value
            db.commit()
            allowed_id = allowed.id
            denied_id = denied.id
        finally:
            db.close()

        headers = self._login(self.member_email)
        listed = self.client.get(f"/documents/workspaces/{self.workspace_id}", headers=headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        ids = {row["id"] for row in listed.json()}
        self.assertEqual(ids, {str(allowed_id)})

        ok = self.client.get(f"/documents/{allowed_id}", headers=headers)
        self.assertEqual(ok.status_code, 200, ok.text)
        blocked = self.client.get(f"/documents/{denied_id}", headers=headers)
        self.assertEqual(blocked.status_code, 404, blocked.text)


if __name__ == "__main__":
    unittest.main()
