from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models import Document, DocumentChunk, Organization, Workspace
from app.services.embeddings import EmbeddingServiceError
from app.services.ingestion_service import IngestDocumentParams, ingest_document


class _SuccessfulEmbeddingClient:
    def embed_texts_batched(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * settings.embedding_dimensions for _ in texts]


class _FailingEmbeddingClient:
    def embed_texts_batched(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingServiceError("embedding backend unavailable")


class IngestionServiceReindexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.SessionLocal()
        try:
            org = Organization(name="Org", slug="org", tenant_key="tenant", status="active", plan="free_trial")
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Workspace")
            db.add(workspace)
            db.commit()
            self.org_id = org.id
            self.workspace_id = workspace.id
        finally:
            db.close()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _params(self, content: str) -> IngestDocumentParams:
        return IngestDocumentParams(
            content=content,
            name="Handbook",
            source_type="google-drive",
            external_id="doc-1",
            organization_id=self.org_id,
            workspace_id=self.workspace_id,
            metadata={"version": content[:3]},
        )

    def test_failed_reingest_preserves_existing_chunks(self) -> None:
        db = self.SessionLocal()
        try:
            with patch("app.services.ingestion_service.get_embedding_client", return_value=_SuccessfulEmbeddingClient()):
                document_id, chunk_count = ingest_document(db, self._params("old searchable handbook content"))
            self.assertGreater(chunk_count, 0)
            old_chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index.asc())
                .all()
            )
            self.assertGreater(len(old_chunks), 0)
            old_contents = [chunk.content for chunk in old_chunks]

            with patch("app.services.ingestion_service.get_embedding_client", return_value=_FailingEmbeddingClient()):
                with self.assertRaises(EmbeddingServiceError):
                    ingest_document(db, self._params("new content that cannot be embedded"))

            doc = db.get(Document, document_id)
            self.assertIsNotNone(doc)
            remaining_chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index.asc())
                .all()
            )
            self.assertEqual([chunk.content for chunk in remaining_chunks], old_contents)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

