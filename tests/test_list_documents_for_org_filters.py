"""Regression: org document listing must accept workspace_id / q filters under SQLAlchemy 2.x."""

from __future__ import annotations

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Document, DocumentStatus, Organization, OrgStatus, Workspace
from app.services.metrics import list_documents_for_org


class ListDocumentsForOrgFiltersTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()
        self.org = Organization(
            id=uuid4(),
            name="Acme",
            slug=f"acme-{uuid4().hex[:8]}",
            tenant_key=f"tenant-{uuid4().hex[:8]}",
            status=OrgStatus.active.value,
        )
        self.ws_a = Workspace(id=uuid4(), organization_id=self.org.id, name="Alpha")
        self.ws_b = Workspace(id=uuid4(), organization_id=self.org.id, name="Beta")
        self.db.add_all([self.org, self.ws_a, self.ws_b])
        self.db.flush()
        self.doc_a = Document(
            organization_id=self.org.id,
            workspace_id=self.ws_a.id,
            filename="alpha-contract.pdf",
            content_type="application/pdf",
            storage_path="inline://a",
            source_type="pdf-upload",
            status=DocumentStatus.indexed.value,
        )
        self.doc_b = Document(
            organization_id=self.org.id,
            workspace_id=self.ws_b.id,
            filename="beta-notes.txt",
            content_type="text/plain",
            storage_path="inline://b",
            source_type="file-upload",
            status=DocumentStatus.indexed.value,
        )
        self.db.add_all([self.doc_a, self.doc_b])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_filter_by_workspace_id(self) -> None:
        rows = list_documents_for_org(
            self.db,
            organization_id=self.org.id,
            workspace_id=self.ws_a.id,
        )
        self.assertEqual([r["id"] for r in rows], [str(self.doc_a.id)])
        self.assertEqual(rows[0]["workspace_name"], "Alpha")

    def test_filter_by_filename_query(self) -> None:
        rows = list_documents_for_org(
            self.db,
            organization_id=self.org.id,
            q="notes",
        )
        self.assertEqual([r["id"] for r in rows], [str(self.doc_b.id)])

    def test_unfiltered_lists_all(self) -> None:
        rows = list_documents_for_org(self.db, organization_id=self.org.id)
        self.assertEqual({r["id"] for r in rows}, {str(self.doc_a.id), str(self.doc_b.id)})


if __name__ == "__main__":
    unittest.main()
