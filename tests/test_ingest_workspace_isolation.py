"""Regression: ingest identity must be workspace-scoped."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models import Document, DocumentChunk, Organization, OrgStatus, Workspace
from app.services.ingestion_service import IngestDocumentParams, ingest_document


class _FakeEmbeddingClient:
    def embed_texts_batched(self, texts, **kwargs):
        dim = settings.embedding_dimensions
        return [[0.0] * dim for _ in texts]


class IngestWorkspaceIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        org = Organization(
            name="Multi-WS Org",
            slug=f"multi-{uuid4().hex[:8]}",
            tenant_key=f"tenant-{uuid4().hex[:8]}",
            status=OrgStatus.active.value,
            plan="free",
        )
        self.db.add(org)
        self.db.flush()
        self.org_id = org.id
        self.ws_a = Workspace(organization_id=org.id, name="Workspace A")
        self.ws_b = Workspace(organization_id=org.id, name="Workspace B")
        self.db.add_all([self.ws_a, self.ws_b])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_same_external_id_creates_separate_documents_per_workspace(self) -> None:
        """
        Concrete trigger: two workspaces in one org sync/ingest the same connector
        external_id. Pre-fix, workspace B overwrote workspace A's document/chunks.
        """
        external_id = "drive-file-shared-123"
        with patch(
            "app.services.ingestion_service.get_embedding_client",
            return_value=_FakeEmbeddingClient(),
        ):
            doc_a_id, _ = ingest_document(
                self.db,
                IngestDocumentParams(
                    content="Confidential content belonging to workspace A only.",
                    name="A Doc",
                    source_type="google-drive",
                    external_id=external_id,
                    organization_id=self.org_id,
                    workspace_id=self.ws_a.id,
                ),
            )
            doc_b_id, _ = ingest_document(
                self.db,
                IngestDocumentParams(
                    content="Different content belonging to workspace B only.",
                    name="B Doc",
                    source_type="google-drive",
                    external_id=external_id,
                    organization_id=self.org_id,
                    workspace_id=self.ws_b.id,
                ),
            )

        self.assertNotEqual(doc_a_id, doc_b_id)
        doc_a = self.db.get(Document, doc_a_id)
        doc_b = self.db.get(Document, doc_b_id)
        assert doc_a is not None and doc_b is not None
        self.assertEqual(doc_a.workspace_id, self.ws_a.id)
        self.assertEqual(doc_b.workspace_id, self.ws_b.id)
        self.assertEqual(doc_a.filename, "A Doc")
        self.assertEqual(doc_b.filename, "B Doc")

        chunks_a = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_a_id).all()
        chunks_b = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_b_id).all()
        self.assertTrue(any("workspace A" in c.content for c in chunks_a))
        self.assertTrue(any("workspace B" in c.content for c in chunks_b))
        self.assertFalse(any("workspace B" in c.content for c in chunks_a))
        self.assertEqual(self.db.query(Document).count(), 2)

    def test_reingest_same_workspace_updates_existing_document(self) -> None:
        external_id = "drive-file-resynced"
        with patch(
            "app.services.ingestion_service.get_embedding_client",
            return_value=_FakeEmbeddingClient(),
        ):
            first_id, _ = ingest_document(
                self.db,
                IngestDocumentParams(
                    content="Original workspace A body text for reindex.",
                    name="Original",
                    source_type="google-drive",
                    external_id=external_id,
                    organization_id=self.org_id,
                    workspace_id=self.ws_a.id,
                ),
            )
            second_id, _ = ingest_document(
                self.db,
                IngestDocumentParams(
                    content="Updated workspace A body text after reindex.",
                    name="Updated",
                    source_type="google-drive",
                    external_id=external_id,
                    organization_id=self.org_id,
                    workspace_id=self.ws_a.id,
                ),
            )

        self.assertEqual(first_id, second_id)
        doc = self.db.get(Document, first_id)
        assert doc is not None
        self.assertEqual(doc.filename, "Updated")
        self.assertEqual(doc.workspace_id, self.ws_a.id)
        chunks = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == first_id).all()
        self.assertTrue(any("Updated workspace A" in c.content for c in chunks))
        self.assertEqual(self.db.query(Document).filter(Document.workspace_id == self.ws_a.id).count(), 1)


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revision_ids_are_unique_and_linear(self) -> None:
        from pathlib import Path
        import re

        versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        revision_re = re.compile(r'^revision:\s*str\s*=\s*["\']([^"\']+)["\']', re.M)
        down_re = re.compile(r'^down_revision:\s*(?:Union\[[^\]]+\]|[^=]+)=\s*([^\n]+)', re.M)

        revisions: dict[str, str | None] = {}
        for path in sorted(versions.glob("*.py")):
            text = path.read_text()
            rev_match = revision_re.search(text)
            self.assertIsNotNone(rev_match, f"missing revision in {path.name}")
            rev = rev_match.group(1)
            self.assertNotIn(rev, revisions, f"duplicate revision id {rev} in {path.name}")
            down_match = down_re.search(text)
            self.assertIsNotNone(down_match, f"missing down_revision in {path.name}")
            down_raw = down_match.group(1).strip()
            if down_raw in ("None", "none"):
                down: str | None = None
            else:
                down = down_raw.strip("\"'")
            revisions[rev] = down

        roots = [r for r, d in revisions.items() if d is None]
        self.assertEqual(len(roots), 1, f"expected one root, got {roots}")
        children: dict[str | None, list[str]] = {}
        for rev, down in revisions.items():
            children.setdefault(down, []).append(rev)
        for parent, kids in children.items():
            self.assertEqual(len(kids), 1, f"multiple children of {parent}: {kids}")

        # Walk to a single head that includes the workspace-scoped index migration.
        current = roots[0]
        seen = {current}
        while current in children:
            current = children[current][0]
            self.assertNotIn(current, seen)
            seen.add(current)
        self.assertEqual(current, "023")
        self.assertEqual(seen, set(revisions))


if __name__ == "__main__":
    unittest.main()
