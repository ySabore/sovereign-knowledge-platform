"""Regression: suspended orgs must lock out members; only platform owners delete/suspend."""

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
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)


class OrgStatusAndDeleteRbacTests(unittest.TestCase):
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
            self.platform_owner = User(
                email="platform-owner-status@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Platform Owner",
                is_active=True,
                is_platform_owner=True,
            )
            self.org_owner = User(
                email="org-owner-status@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Org Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.member = User(
                email="member-status@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Member",
                is_active=True,
                is_platform_owner=False,
            )
            db.add_all([self.platform_owner, self.org_owner, self.member])
            db.flush()

            org = Organization(
                name="Status Org",
                slug=f"status-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            self.org_id = org.id
            self.org_slug = org.slug

            ws = Workspace(organization_id=org.id, name="General", description="Default")
            db.add(ws)
            db.flush()
            self.workspace_id = ws.id

            db.add_all(
                [
                    OrganizationMembership(
                        user_id=self.org_owner.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.org_owner.value,
                    ),
                    OrganizationMembership(
                        user_id=self.member.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    WorkspaceMember(
                        user_id=self.org_owner.id,
                        workspace_id=ws.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                    WorkspaceMember(
                        user_id=self.member.id,
                        workspace_id=ws.id,
                        role=WorkspaceMemberRole.member.value,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

    def _token(self, email: str) -> str:
        r = self.client.post("/auth/login", json={"email": email, "password": "ChangeMeNow!"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def _auth(self, email: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token(email)}"}

    def test_org_owner_cannot_suspend_organization(self) -> None:
        r = self.client.patch(
            f"/organizations/{self.org_id}",
            headers=self._auth("org-owner-status@example.com"),
            json={"status": "suspended"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertIn("platform owners", r.json()["detail"].lower())

    def test_platform_owner_can_suspend_and_members_are_locked_out(self) -> None:
        r = self.client.patch(
            f"/organizations/{self.org_id}",
            headers=self._auth("platform-owner-status@example.com"),
            json={"status": "suspended"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "suspended")

        denied = self.client.get(
            f"/organizations/{self.org_id}",
            headers=self._auth("org-owner-status@example.com"),
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertIn("suspended", denied.json()["detail"].lower())

        ws_denied = self.client.get(
            f"/workspaces/{self.workspace_id}",
            headers=self._auth("member-status@example.com"),
        )
        self.assertEqual(ws_denied.status_code, 403, ws_denied.text)

        # Platform owner retains support access.
        ok = self.client.get(
            f"/organizations/{self.org_id}",
            headers=self._auth("platform-owner-status@example.com"),
        )
        self.assertEqual(ok.status_code, 200, ok.text)

    def test_org_owner_cannot_hard_delete_organization(self) -> None:
        r = self.client.delete(
            f"/organizations/{self.org_id}",
            headers=self._auth("org-owner-status@example.com"),
            params={"confirm_slug": self.org_slug},
        )
        self.assertEqual(r.status_code, 403, r.text)

        still = self.client.get(
            f"/organizations/{self.org_id}",
            headers=self._auth("org-owner-status@example.com"),
        )
        self.assertEqual(still.status_code, 200, still.text)

    def test_platform_owner_can_hard_delete_organization(self) -> None:
        r = self.client.delete(
            f"/organizations/{self.org_id}",
            headers=self._auth("platform-owner-status@example.com"),
            params={"confirm_slug": self.org_slug},
        )
        self.assertEqual(r.status_code, 204, r.text)

        gone = self.client.get(
            f"/organizations/{self.org_id}",
            headers=self._auth("platform-owner-status@example.com"),
        )
        self.assertEqual(gone.status_code, 404, gone.text)


if __name__ == "__main__":
    unittest.main()
