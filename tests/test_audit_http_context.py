"""Path → org/workspace resolution for audit HTTP middleware."""

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ChatSession, Organization, User, Workspace
from app.services.audit_http_context import resolve_audit_org_workspace


class AuditHttpContextTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = self.Session()
        try:
            self.org_id = uuid4()
            self.ws_id = uuid4()
            uid = uuid4()
            db.add(Organization(id=self.org_id, name="O", slug="o", tenant_key="t", status="active", plan="free_trial"))
            db.add(User(id=uid, email="a@a.com", password_hash="x", is_active=True, is_platform_owner=False))
            db.flush()
            db.add(
                Workspace(
                    id=self.ws_id,
                    organization_id=self.org_id,
                    name="W",
                    description=None,
                    created_by=uid,
                )
            )
            db.flush()
            self.sess_id = uuid4()
            db.add(
                ChatSession(
                    id=self.sess_id,
                    organization_id=self.org_id,
                    workspace_id=self.ws_id,
                    user_id=uid,
                    title="T",
                )
            )
            db.commit()
        finally:
            db.close()

    def test_organizations_prefix_returns_org_only(self) -> None:
        db = self.Session()
        try:
            oid, wid = resolve_audit_org_workspace(db, f"/organizations/{self.org_id}/members")
            self.assertEqual(oid, self.org_id)
            self.assertIsNone(wid)
        finally:
            db.close()

    def test_documents_workspace_prefix(self) -> None:
        db = self.Session()
        try:
            oid, wid = resolve_audit_org_workspace(db, f"/documents/workspaces/{self.ws_id}/upload")
            self.assertEqual(oid, self.org_id)
            self.assertEqual(wid, self.ws_id)
        finally:
            db.close()

    def test_chat_session_prefix(self) -> None:
        db = self.Session()
        try:
            oid, wid = resolve_audit_org_workspace(db, f"/chat/sessions/{self.sess_id}/messages")
            self.assertEqual(oid, self.org_id)
            self.assertEqual(wid, self.ws_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
