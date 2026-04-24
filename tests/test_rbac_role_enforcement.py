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
    AuditLog,
    Document,
    IntegrationConnector,
    Organization,
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)


class RBACRoleEnforcementTests(unittest.TestCase):
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
            self.org_owner = User(
                email="org-owner-rbac@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Org Owner",
                is_active=True,
                is_platform_owner=False,
            )
            self.ws_admin = User(
                email="ws-admin-rbac@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Workspace Admin",
                is_active=True,
                is_platform_owner=False,
            )
            self.editor = User(
                email="editor-rbac@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Editor",
                is_active=True,
                is_platform_owner=False,
            )
            self.member = User(
                email="member-rbac@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Member",
                is_active=True,
                is_platform_owner=False,
            )
            self.org_only_member = User(
                email="org-only-rbac@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Org-only Member",
                is_active=True,
                is_platform_owner=False,
            )
            db.add_all([self.org_owner, self.ws_admin, self.editor, self.member, self.org_only_member])
            db.flush()

            org = Organization(
                name="RBAC Org",
                slug=f"rbac-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            self.org_id = org.id

            ws = Workspace(organization_id=org.id, name="Assigned Workspace", description="Primary test workspace")
            ws_unassigned = Workspace(organization_id=org.id, name="Unassigned Workspace", description="No member rows")
            db.add_all([ws, ws_unassigned])
            db.flush()
            self.workspace_id = ws.id
            self.workspace_unassigned_id = ws_unassigned.id

            db.add_all(
                [
                    OrganizationMembership(
                        user_id=self.org_owner.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.org_owner.value,
                    ),
                    OrganizationMembership(
                        user_id=self.ws_admin.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    OrganizationMembership(
                        user_id=self.editor.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    OrganizationMembership(
                        user_id=self.member.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    OrganizationMembership(
                        user_id=self.org_only_member.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    WorkspaceMember(
                        user_id=self.ws_admin.id,
                        workspace_id=ws.id,
                        role=WorkspaceMemberRole.workspace_admin.value,
                    ),
                    WorkspaceMember(
                        user_id=self.editor.id,
                        workspace_id=ws.id,
                        role=WorkspaceMemberRole.editor.value,
                    ),
                    WorkspaceMember(
                        user_id=self.member.id,
                        workspace_id=ws.id,
                        role=WorkspaceMemberRole.member.value,
                    ),
                ]
            )
            db.flush()

            self.editor_doc = Document(
                organization_id=org.id,
                workspace_id=ws.id,
                created_by=self.editor.id,
                filename="editor-owned.txt",
                content_type="text/plain",
                storage_path="",
                source_type="file-upload",
                external_id=str(uuid4()),
                status="indexed",
                page_count=1,
            )
            self.other_doc = Document(
                organization_id=org.id,
                workspace_id=ws.id,
                created_by=self.member.id,
                filename="member-owned.txt",
                content_type="text/plain",
                storage_path="",
                source_type="file-upload",
                external_id=str(uuid4()),
                status="indexed",
                page_count=1,
            )
            db.add_all([self.editor_doc, self.other_doc])
            db.flush()
            self.connector = IntegrationConnector(
                organization_id=org.id,
                connector_type="google-drive",
                nango_connection_id="conn-rbac-1",
                status="active",
                config={"workspace_id": str(ws_unassigned.id), "workspace_ids": [str(ws_unassigned.id)]},
            )
            db.add(self.connector)
            db.flush()

            db.add_all(
                [
                    AuditLog(
                        actor_user_id=self.org_owner.id,
                        organization_id=org.id,
                        workspace_id=ws.id,
                        action="workspace_updated",
                        target_type="workspace",
                        target_id=ws.id,
                        metadata_json={"scope": "managed"},
                    ),
                    AuditLog(
                        actor_user_id=self.org_owner.id,
                        organization_id=org.id,
                        workspace_id=ws_unassigned.id,
                        action="workspace_updated",
                        target_type="workspace",
                        target_id=ws_unassigned.id,
                        metadata_json={"scope": "unmanaged"},
                    ),
                    AuditLog(
                        actor_user_id=self.org_owner.id,
                        organization_id=org.id,
                        workspace_id=None,
                        action="organization_updated",
                        target_type="organization",
                        target_id=org.id,
                        metadata_json={"scope": "org"},
                    ),
                ]
            )
            db.commit()
            db.refresh(self.editor_doc)
            db.refresh(self.other_doc)
            db.refresh(self.connector)
        finally:
            db.close()

    def _login(self, email: str, password: str = "ChangeMeNow!") -> dict[str, str]:
        resp = self.client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_org_member_without_workspace_assignment_cannot_open_workspace(self) -> None:
        headers = self._login("org-only-rbac@example.com")
        resp = self.client.get(f"/workspaces/{self.workspace_id}", headers=headers)
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_org_owner_can_open_workspace_without_workspace_membership(self) -> None:
        headers = self._login("org-owner-rbac@example.com")
        resp = self.client.get(f"/workspaces/{self.workspace_unassigned_id}", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_editor_can_delete_only_own_document(self) -> None:
        headers = self._login("editor-rbac@example.com")
        own_resp = self.client.delete(f"/documents/{self.editor_doc.id}", headers=headers)
        self.assertEqual(own_resp.status_code, 204, own_resp.text)

        other_resp = self.client.delete(f"/documents/{self.other_doc.id}", headers=headers)
        self.assertEqual(other_resp.status_code, 403, other_resp.text)

    def test_member_cannot_view_connectors(self) -> None:
        headers = self._login("member-rbac@example.com")
        resp = self.client.get(f"/connectors/organization/{self.org_id}", headers=headers)
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_workspace_admin_audit_is_scoped_to_managed_workspaces(self) -> None:
        headers = self._login("ws-admin-rbac@example.com")
        resp = self.client.get(f"/organizations/{self.org_id}/audit", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(r.get("workspace_id") == str(self.workspace_id) for r in rows), rows)

    def test_workspace_admin_cannot_filter_audit_to_unmanaged_workspace(self) -> None:
        headers = self._login("ws-admin-rbac@example.com")
        resp = self.client.get(
            f"/organizations/{self.org_id}/audit",
            params={"workspace_id": str(self.workspace_unassigned_id)},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_workspace_admin_can_assign_connector_to_managed_workspace(self) -> None:
        headers = self._login("ws-admin-rbac@example.com")
        resp = self.client.put(
            f"/connectors/{self.connector.id}/workspaces/{self.workspace_id}",
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn(str(self.workspace_id), body.get("workspace_ids", []))

    def test_workspace_admin_cannot_remove_connector_from_unmanaged_workspace(self) -> None:
        headers = self._login("ws-admin-rbac@example.com")
        resp = self.client.delete(
            f"/connectors/{self.connector.id}/workspaces/{self.workspace_unassigned_id}",
            headers=headers,
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_workspace_admin_can_patch_drive_scope_for_managed_workspace(self) -> None:
        headers = self._login("ws-admin-rbac@example.com")
        assign = self.client.put(
            f"/connectors/{self.connector.id}/workspaces/{self.workspace_id}",
            headers=headers,
        )
        self.assertEqual(assign.status_code, 200, assign.text)
        resp = self.client.patch(
            f"/connectors/{self.connector.id}/config",
            json={
                "workspace_id": str(self.workspace_id),
                "drive_folder_ids": ["folderA", "folderB"],
                "drive_include_subfolders": False,
            },
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body.get("workspace_id"), str(self.workspace_id))
        self.assertEqual(body.get("drive_sync", {}).get("folder_ids"), ["folderA", "folderB"])
        self.assertFalse(body.get("drive_sync", {}).get("include_subfolders", True))

        db = self.SessionLocal()
        try:
            conn = db.get(IntegrationConnector, self.connector.id)
            self.assertIsNotNone(conn)
            cfg = conn.config if isinstance(conn.config, dict) else {}
            ws_settings = cfg.get("workspace_settings")
            self.assertIsInstance(ws_settings, dict)
            ws_cfg = ws_settings.get(str(self.workspace_id))
            self.assertIsInstance(ws_cfg, dict)
            self.assertEqual(ws_cfg.get("drive_folder_ids"), ["folderA", "folderB"])
            self.assertFalse(bool(ws_cfg.get("drive_include_subfolders", True)))
        finally:
            db.close()

    def test_workspace_admin_cannot_patch_drive_scope_for_unmanaged_workspace(self) -> None:
        headers = self._login("ws-admin-rbac@example.com")
        resp = self.client.patch(
            f"/connectors/{self.connector.id}/config",
            json={
                "workspace_id": str(self.workspace_unassigned_id),
                "drive_folder_ids": ["folderA"],
                "drive_include_subfolders": True,
            },
            headers=headers,
        )
        self.assertEqual(resp.status_code, 403, resp.text)


if __name__ == "__main__":
    unittest.main()
