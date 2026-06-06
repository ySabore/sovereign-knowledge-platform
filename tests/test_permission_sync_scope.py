from __future__ import annotations

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, DocumentPermission, Organization, OrgStatus, Workspace
from app.services.permissions import sync_permissions


class PermissionSyncScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_sync_permissions_rejects_document_from_other_org(self) -> None:
        db = self.SessionLocal()
        try:
            org_a = Organization(
                name="Org A",
                slug=f"org-a-{uuid4().hex[:8]}",
                tenant_key=f"tenant-a-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            org_b = Organization(
                name="Org B",
                slug=f"org-b-{uuid4().hex[:8]}",
                tenant_key=f"tenant-b-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add_all([org_a, org_b])
            db.flush()
            workspace_b = Workspace(organization_id=org_b.id, name="Workspace B")
            db.add(workspace_b)
            db.flush()
            doc_b = Document(
                organization_id=org_b.id,
                workspace_id=workspace_b.id,
                filename="other-org.txt",
                content_type="text/plain",
                storage_path="inline://test/other-org",
                source_type="test",
                external_id="external-other",
                status="indexed",
            )
            db.add(doc_b)
            db.commit()

            with self.assertRaises(ValueError):
                sync_permissions(
                    db,
                    "google-drive",
                    [
                        {
                            "document_id": str(doc_b.id),
                            "organization_id": str(org_b.id),
                            "user_id": None,
                            "can_read": True,
                            "source": "google-drive",
                            "external_id": "external-other",
                        }
                    ],
                    organization_id=org_a.id,
                )

            self.assertEqual(db.query(DocumentPermission).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
