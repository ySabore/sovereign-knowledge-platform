"""Deleting an IntegrationConnector must free the OrganizationConnector plan slot."""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models import (
    IntegrationConnector,
    Organization,
    OrganizationConnector,
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.services.billing import (
    count_org_connectors,
    register_connector_integration,
    unregister_connector_integration,
)


class ConnectorSlotCleanupTests(unittest.TestCase):
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
        db = self.SessionLocal()
        try:
            self.owner = User(
                email="slot-owner@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Owner",
                is_active=True,
                is_platform_owner=False,
            )
            db.add(self.owner)
            db.flush()
            org = Organization(
                name="Slot Org",
                slug=f"slot-org-{uuid4().hex[:8]}",
                tenant_key=uuid4().hex,
                status=OrgStatus.active.value,
                plan="free",
            )
            db.add(org)
            db.flush()
            self.org_id = org.id
            db.add(
                OrganizationMembership(
                    user_id=self.owner.id,
                    organization_id=org.id,
                    role=OrgMembershipRole.org_owner.value,
                )
            )
            ws = Workspace(organization_id=org.id, name="General", created_by=self.owner.id)
            db.add(ws)
            db.flush()
            self.workspace_id = ws.id
            db.add(
                WorkspaceMember(
                    workspace_id=ws.id,
                    user_id=self.owner.id,
                    role=WorkspaceMemberRole.workspace_admin.value,
                )
            )
            conn = IntegrationConnector(
                organization_id=org.id,
                connector_type="google-drive",
                nango_connection_id="nango-slot-1",
                status="active",
                config={"workspace_id": str(ws.id), "workspace_ids": [str(ws.id)]},
            )
            db.add(conn)
            db.flush()
            self.connector_id = conn.id
            register_connector_integration(db, org.id, "google-drive")
            db.commit()
        finally:
            db.close()

    def _login(self) -> dict[str, str]:
        resp = self.client.post(
            "/auth/login",
            json={"email": "slot-owner@example.com", "password": "ChangeMeNow!"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_unregister_helper_removes_billing_registration(self) -> None:
        db = self.SessionLocal()
        try:
            self.assertEqual(count_org_connectors(db, self.org_id), 1)
            unregister_connector_integration(db, self.org_id, "google-drive")
            db.commit()
            self.assertEqual(count_org_connectors(db, self.org_id), 0)
        finally:
            db.close()

    def test_delete_connector_frees_plan_slot(self) -> None:
        headers = self._login()
        resp = self.client.delete(f"/connectors/{self.connector_id}", headers=headers)
        self.assertEqual(resp.status_code, 204, resp.text)

        db = self.SessionLocal()
        try:
            self.assertIsNone(db.get(IntegrationConnector, self.connector_id))
            remaining = (
                db.query(func.count(OrganizationConnector.id))
                .filter(OrganizationConnector.organization_id == self.org_id)
                .scalar()
            )
            self.assertEqual(int(remaining or 0), 0)
        finally:
            db.close()

    def test_remove_last_workspace_assignment_frees_plan_slot(self) -> None:
        headers = self._login()
        resp = self.client.delete(
            f"/connectors/{self.connector_id}/workspaces/{self.workspace_id}",
            headers=headers,
        )
        self.assertEqual(resp.status_code, 204, resp.text)

        db = self.SessionLocal()
        try:
            self.assertIsNone(db.get(IntegrationConnector, self.connector_id))
            self.assertEqual(count_org_connectors(db, self.org_id), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
