from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, DocumentChunk, DocumentStatus, Organization, OrgStatus, Workspace
from app.services.embeddings import EmbeddingServiceError
from app.services.ingestion_service import IngestDocumentParams, ingest_document


class _FailingEmbeddingClient:
    def embed_texts_batched(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingServiceError("embedding backend unavailable")


class IngestionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def test_existing_document_chunks_survive_embedding_failure(self) -> None:
        db = self.SessionLocal()
        try:
            org = Organization(
                name="Ingestion Org",
                slug=f"ingestion-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()

            workspace = Workspace(organization_id=org.id, name="Knowledge")
            db.add(workspace)
            db.flush()

            document = Document(
                organization_id=org.id,
                workspace_id=workspace.id,
                filename="Original Drive Doc",
                content_type="text/plain",
                storage_path="inline://google-drive/doc-1",
                source_type="google-drive",
                external_id="doc-1",
                status=DocumentStatus.indexed.value,
            )
            db.add(document)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=1,
                    content="original searchable content",
                    token_count=27,
                    embedding_model="test-model",
                    embedding=None,
                )
            )
            org_id = org.id
            workspace_id = workspace.id
            document_id = document.id
            db.commit()

            with patch("app.services.ingestion_service.get_embedding_client", return_value=_FailingEmbeddingClient()):
                with self.assertRaises(EmbeddingServiceError):
                    ingest_document(
                        db,
                        IngestDocumentParams(
                            content="updated connector content",
                            name="Updated Drive Doc",
                            source_type="google-drive",
                            external_id="doc-1",
                            organization_id=org_id,
                            workspace_id=workspace_id,
                        ),
                    )

            restored = db.query(Document).filter(Document.id == document_id).one()
            self.assertEqual(restored.status, DocumentStatus.indexed.value)
            self.assertEqual(restored.filename, "Original Drive Doc")
            self.assertEqual(
                db.query(func.count(DocumentChunk.id)).filter(DocumentChunk.document_id == document_id).scalar(),
                1,
            )
            chunk = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).one()
            self.assertEqual(chunk.content, "original searchable content")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
