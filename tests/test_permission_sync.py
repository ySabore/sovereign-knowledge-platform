from __future__ import annotations

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, DocumentPermission, Organization, OrgStatus, Workspace
from app.services.permissions import sync_permissions


class PermissionSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._seed()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed(self) -> None:
        db = self.SessionLocal()
        try:
            org_a = Organization(
                name="Permission Org A",
                slug=f"permission-a-{uuid4().hex[:8]}",
                tenant_key=f"tenant-a-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            org_b = Organization(
                name="Permission Org B",
                slug=f"permission-b-{uuid4().hex[:8]}",
                tenant_key=f"tenant-b-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add_all([org_a, org_b])
            db.flush()
            workspace_a = Workspace(organization_id=org_a.id, name="Workspace A")
            workspace_b = Workspace(organization_id=org_b.id, name="Workspace B")
            db.add_all([workspace_a, workspace_b])
            db.flush()
            doc_a = Document(
                organization_id=org_a.id,
                workspace_id=workspace_a.id,
                filename="a.txt",
                content_type="text/plain",
                storage_path="inline://a",
                source_type="google-drive",
                external_id="doc-a",
            )
            doc_b = Document(
                organization_id=org_b.id,
                workspace_id=workspace_b.id,
                filename="b.txt",
                content_type="text/plain",
                storage_path="inline://b",
                source_type="google-drive",
                external_id="doc-b",
            )
            db.add_all([doc_a, doc_b])
            db.commit()
            self.org_a_id = org_a.id
            self.org_b_id = org_b.id
            self.doc_a_id = doc_a.id
            self.doc_b_id = doc_b.id
        finally:
            db.close()

    def _permission_count(self) -> int:
        db = self.SessionLocal()
        try:
            return db.query(DocumentPermission).count()
        finally:
            db.close()

    def test_valid_permission_sync_writes_acl(self) -> None:
        db = self.SessionLocal()
        try:
            updated = sync_permissions(
                db,
                "google-drive",
                [
                    {
                        "document_id": str(self.doc_a_id),
                        "organization_id": str(self.org_a_id),
                        "user_id": None,
                        "can_read": True,
                        "source": "google-drive",
                        "external_id": "doc-a",
                    }
                ],
                organization_id=self.org_a_id,
            )
            self.assertEqual(updated, 1)
            self.assertEqual(db.query(DocumentPermission).count(), 1)
        finally:
            db.close()

    def test_mixed_organization_payload_is_rejected_before_any_write(self) -> None:
        db = self.SessionLocal()
        try:
            with self.assertRaisesRegex(ValueError, "authorized organization"):
                sync_permissions(
                    db,
                    "google-drive",
                    [
                        {
                            "document_id": str(self.doc_a_id),
                            "organization_id": str(self.org_a_id),
                            "user_id": None,
                            "can_read": True,
                            "source": "google-drive",
                            "external_id": "doc-a",
                        },
                        {
                            "document_id": str(self.doc_b_id),
                            "organization_id": str(self.org_b_id),
                            "user_id": None,
                            "can_read": True,
                            "source": "google-drive",
                            "external_id": "doc-b",
                        },
                    ],
                    organization_id=self.org_a_id,
                )
            self.assertEqual(db.query(DocumentPermission).count(), 0)
        finally:
            db.close()

    def test_forged_organization_id_for_foreign_document_is_rejected(self) -> None:
        db = self.SessionLocal()
        try:
            with self.assertRaisesRegex(ValueError, "organization mismatch"):
                sync_permissions(
                    db,
                    "google-drive",
                    [
                        {
                            "document_id": str(self.doc_b_id),
                            "organization_id": str(self.org_a_id),
                            "user_id": None,
                            "can_read": True,
                            "source": "google-drive",
                            "external_id": "doc-b",
                        }
                    ],
                    organization_id=self.org_a_id,
                )
            self.assertEqual(db.query(DocumentPermission).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
