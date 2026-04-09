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
from app.models import Organization, OrganizationMembership, OrgMembershipRole, OrgStatus, User, Workspace, WorkspaceMember, WorkspaceMemberRole


class MembershipVisibilityRBACTests(unittest.TestCase):
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
            self.org_owner = User(email="org-owner@example.com", password_hash=hash_password("ChangeMeNow!"), full_name="Org Owner", is_active=True, is_platform_owner=False)
            self.ws_admin = User(email="ws-admin@example.com", password_hash=hash_password("ChangeMeNow!"), full_name="Workspace Admin", is_active=True, is_platform_owner=False)
            self.org_member = User(email="org-member@example.com", password_hash=hash_password("ChangeMeNow!"), full_name="Org Member", is_active=True, is_platform_owner=False)
            self.ws_member = User(email="ws-member@example.com", password_hash=hash_password("ChangeMeNow!"), full_name="Workspace Member", is_active=True, is_platform_owner=False)
            self.platform_owner = User(email="platform-owner@example.com", password_hash=hash_password("ChangeMeNow!"), full_name="Platform Owner", is_active=True, is_platform_owner=True)
            db.add_all([self.org_owner, self.ws_admin, self.org_member, self.ws_member, self.platform_owner])
            db.flush()

            org = Organization(name="Demo Org", slug=f"demo-{uuid4().hex[:8]}", tenant_key="tenant", status=OrgStatus.active.value)
            db.add(org)
            db.flush()
            self.org_id = org.id

            workspace = Workspace(organization_id=org.id, name="Pilot Workspace", description="Test")
            db.add(workspace)
            db.flush()
            self.workspace_id = workspace.id

            db.add_all([
                OrganizationMembership(user_id=self.org_owner.id, organization_id=org.id, role=OrgMembershipRole.org_owner.value),
                OrganizationMembership(user_id=self.ws_admin.id, organization_id=org.id, role=OrgMembershipRole.member.value),
                OrganizationMembership(user_id=self.org_member.id, organization_id=org.id, role=OrgMembershipRole.member.value),
                OrganizationMembership(user_id=self.ws_member.id, organization_id=org.id, role=OrgMembershipRole.member.value),
                WorkspaceMember(user_id=self.org_owner.id, workspace_id=workspace.id, role=WorkspaceMemberRole.workspace_admin.value),
                WorkspaceMember(user_id=self.ws_admin.id, workspace_id=workspace.id, role=WorkspaceMemberRole.workspace_admin.value),
                WorkspaceMember(user_id=self.org_member.id, workspace_id=workspace.id, role=WorkspaceMemberRole.member.value),
                WorkspaceMember(user_id=self.ws_member.id, workspace_id=workspace.id, role=WorkspaceMemberRole.member.value),
            ])
            db.commit()
        finally:
            db.close()

    def _login(self, email: str, password: str = "ChangeMeNow!") -> dict[str, str]:
        resp = self.client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_org_owner_can_list_org_and_workspace_members(self) -> None:
        headers = self._login("org-owner@example.com")
        org_resp = self.client.get(f"/organizations/{self.org_id}/members", headers=headers)
        ws_resp = self.client.get(f"/workspaces/{self.workspace_id}/members", headers=headers)
        self.assertEqual(org_resp.status_code, 200, org_resp.text)
        self.assertEqual(ws_resp.status_code, 200, ws_resp.text)

    def test_platform_owner_can_list_org_members(self) -> None:
        headers = self._login("platform-owner@example.com")
        org_resp = self.client.get(f"/organizations/{self.org_id}/members", headers=headers)
        self.assertEqual(org_resp.status_code, 200, org_resp.text)

    def test_non_owner_roles_cannot_list_org_members(self) -> None:
        for email in ["ws-admin@example.com", "org-member@example.com", "ws-member@example.com"]:
            with self.subTest(email=email):
                headers = self._login(email)
                resp = self.client.get(f"/organizations/{self.org_id}/members", headers=headers)
                self.assertEqual(resp.status_code, 403, resp.text)

    def test_only_workspace_admin_and_org_owner_can_list_workspace_members(self) -> None:
        allowed = {
            "org-owner@example.com": 200,
            "ws-admin@example.com": 200,
            "org-member@example.com": 403,
            "ws-member@example.com": 403,
        }
        for email, expected in allowed.items():
            with self.subTest(email=email):
                headers = self._login(email)
                resp = self.client.get(f"/workspaces/{self.workspace_id}/members", headers=headers)
                self.assertEqual(resp.status_code, expected, resp.text)


if __name__ == "__main__":
    unittest.main()
