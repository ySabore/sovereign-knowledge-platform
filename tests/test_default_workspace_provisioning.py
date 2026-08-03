"""Default General workspace must remain usable for invite / member provisioning."""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, hash_password
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


class DefaultWorkspaceProvisioningTests(unittest.TestCase):
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

    def _auth(self, user_id) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user_id)}"}

    def _seed(self) -> None:
        db = self.SessionLocal()
        try:
            self.owner = User(
                email="owner-default-ws@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.invitee = User(
                email="invitee-default-ws@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Invitee",
                is_active=True,
                is_platform_owner=False,
            )
            db.add_all([self.owner, self.invitee])
            db.flush()

            self.org = Organization(
                name="Default WS Org",
                slug=f"default-ws-{uuid4().hex[:8]}",
                tenant_key=f"t-{uuid4().hex[:10]}",
                status=OrgStatus.active.value,
                plan="team",
            )
            db.add(self.org)
            db.flush()
            db.add(
                OrganizationMembership(
                    user_id=self.owner.id,
                    organization_id=self.org.id,
                    role=OrgMembershipRole.org_owner.value,
                )
            )
            self.general = Workspace(
                organization_id=self.org.id,
                name=DEFAULT_WORKSPACE_NAME,
                description="Default",
                created_by=self.owner.id,
            )
            db.add(self.general)
            db.flush()
            db.add(
                WorkspaceMember(
                    workspace_id=self.general.id,
                    user_id=self.owner.id,
                    role=WorkspaceMemberRole.workspace_admin.value,
                )
            )
            db.commit()
            db.refresh(self.owner)
            db.refresh(self.invitee)
            db.refresh(self.org)
            db.refresh(self.general)
        finally:
            db.close()

    def test_cannot_rename_default_general_workspace(self) -> None:
        res = self.client.patch(
            f"/workspaces/{self.general.id}",
            headers=self._auth(self.owner.id),
            json={"name": "Main"},
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertIn("General", res.json()["detail"])

    def test_cannot_create_duplicate_general_workspace(self) -> None:
        res = self.client.post(
            f"/workspaces/org/{self.org.id}",
            headers=self._auth(self.owner.id),
            json={"name": DEFAULT_WORKSPACE_NAME, "description": "dup"},
        )
        self.assertEqual(res.status_code, 409, res.text)

    def test_cannot_delete_default_general_workspace(self) -> None:
        # Need a second workspace so "last workspace" is not the blocking reason.
        other = self.client.post(
            f"/workspaces/org/{self.org.id}",
            headers=self._auth(self.owner.id),
            json={"name": "Projects", "description": "other"},
        )
        self.assertEqual(other.status_code, 201, other.text)

        res = self.client.delete(
            f"/workspaces/{self.general.id}",
            headers=self._auth(self.owner.id),
            params={"confirm_name": DEFAULT_WORKSPACE_NAME},
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertIn("General", res.json()["detail"])

    def test_member_upsert_still_provisions_when_duplicate_general_rows_exist(self) -> None:
        """Historical duplicate General rows must not 500 member provisioning."""
        db = self.SessionLocal()
        try:
            dup = Workspace(
                organization_id=self.org.id,
                name=DEFAULT_WORKSPACE_NAME,
                description="legacy duplicate",
                created_by=self.owner.id,
            )
            db.add(dup)
            db.commit()
        finally:
            db.close()

        res = self.client.put(
            f"/organizations/{self.org.id}/members",
            headers=self._auth(self.owner.id),
            json={"email": self.invitee.email, "role": "member"},
        )
        self.assertEqual(res.status_code, 200, res.text)

        db = self.SessionLocal()
        try:
            membership = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == self.general.id,
                    WorkspaceMember.user_id == self.invitee.id,
                )
                .one_or_none()
            )
            self.assertIsNotNone(membership)
            self.assertEqual(membership.role, WorkspaceMemberRole.member.value)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
