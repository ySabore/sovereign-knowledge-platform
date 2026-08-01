"""Guards against last-admin demotion via membership upsert."""

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
from app.routers.organizations import DEFAULT_WORKSPACE_NAME


class MembershipUpsertGuardTests(unittest.TestCase):
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
            self.sole_owner = User(
                email="sole-owner@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Sole Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.second_owner = User(
                email="second-owner@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Second Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.ws_admin = User(
                email="ws-admin-upsert@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Workspace Admin",
                is_active=True,
                is_platform_owner=False,
            )
            self.elevated_member = User(
                email="elevated-member@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Elevated Member",
                is_active=True,
                is_platform_owner=False,
            )
            db.add_all([self.sole_owner, self.second_owner, self.ws_admin, self.elevated_member])
            db.flush()

            org = Organization(
                name="Upsert Guard Org",
                slug=f"upsert-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            self.org_id = org.id

            general = Workspace(
                organization_id=org.id,
                name=DEFAULT_WORKSPACE_NAME,
                description="Default workspace",
            )
            extra = Workspace(
                organization_id=org.id,
                name="Extra Workspace",
                description="Secondary workspace",
            )
            db.add_all([general, extra])
            db.flush()
            self.general_id = general.id
            self.extra_id = extra.id

            db.add_all(
                [
                    OrganizationMembership(
                        user_id=self.sole_owner.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.org_owner.value,
                    ),
                    OrganizationMembership(
                        user_id=self.ws_admin.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    OrganizationMembership(
                        user_id=self.elevated_member.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    WorkspaceMember(
                        user_id=self.sole_owner.id,
                        workspace_id=general.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                    WorkspaceMember(
                        user_id=self.ws_admin.id,
                        workspace_id=extra.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                    WorkspaceMember(
                        user_id=self.elevated_member.id,
                        workspace_id=general.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

    def _login(self, email: str) -> dict[str, str]:
        resp = self.client.post("/auth/login", json={"email": email, "password": "ChangeMeNow!"})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_cannot_demote_last_org_owner_via_upsert(self) -> None:
        headers = self._login("sole-owner@example.com")
        resp = self.client.put(
            f"/organizations/{self.org_id}/members",
            json={"email": "sole-owner@example.com", "role": "member"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 409, resp.text)
        self.assertIn("last organization owner", resp.text)

        db = self.SessionLocal()
        try:
            role = (
                db.query(OrganizationMembership.role)
                .filter(
                    OrganizationMembership.organization_id == self.org_id,
                    OrganizationMembership.user_id == self.sole_owner.id,
                )
                .scalar()
            )
            self.assertEqual(role, OrgMembershipRole.org_owner.value)
        finally:
            db.close()

    def test_can_demote_org_owner_when_another_owner_exists(self) -> None:
        db = self.SessionLocal()
        try:
            db.add(
                OrganizationMembership(
                    user_id=self.second_owner.id,
                    organization_id=self.org_id,
                    role=OrgMembershipRole.org_owner.value,
                )
            )
            db.commit()
        finally:
            db.close()

        headers = self._login("sole-owner@example.com")
        resp = self.client.put(
            f"/organizations/{self.org_id}/members",
            json={"email": "sole-owner@example.com", "role": "member"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("role"), "member")

    def test_cannot_demote_last_workspace_admin_via_upsert(self) -> None:
        headers = self._login("sole-owner@example.com")
        resp = self.client.put(
            f"/workspaces/{self.extra_id}/members",
            json={"email": "ws-admin-upsert@example.com", "role": "member"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 409, resp.text)
        self.assertIn("last workspace admin", resp.text)

        db = self.SessionLocal()
        try:
            role = (
                db.query(WorkspaceMember.role)
                .filter(
                    WorkspaceMember.workspace_id == self.extra_id,
                    WorkspaceMember.user_id == self.ws_admin.id,
                )
                .scalar()
            )
            self.assertEqual(role, WorkspaceMemberRole.workspace_admin.value)
        finally:
            db.close()

    def test_org_member_upsert_preserves_elevated_general_workspace_role(self) -> None:
        headers = self._login("sole-owner@example.com")
        # No-op org role upsert must not wipe an intentionally elevated General role.
        resp = self.client.put(
            f"/organizations/{self.org_id}/members",
            json={"email": "elevated-member@example.com", "role": "member"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        db = self.SessionLocal()
        try:
            role = (
                db.query(WorkspaceMember.role)
                .filter(
                    WorkspaceMember.workspace_id == self.general_id,
                    WorkspaceMember.user_id == self.elevated_member.id,
                )
                .scalar()
            )
            self.assertEqual(role, WorkspaceMemberRole.workspace_admin.value)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
