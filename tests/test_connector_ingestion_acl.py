from __future__ import annotations

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models import Document, DocumentPermission, IntegrationConnector, Organization, OrgStatus, Workspace
import app.services.ingestion_service as ingestion_service
from app.services.ingestion_service import IngestDocumentParams, ingest_document


class _EmbeddingClient:
    def embed_texts_batched(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * settings.embedding_dimensions for _ in texts]


class ConnectorIngestionAclTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._orig_rbac_mode = settings.rbac_mode
        self._orig_get_embedding_client = ingestion_service.get_embedding_client
        settings.rbac_mode = "full"
        ingestion_service.get_embedding_client = lambda: _EmbeddingClient()

    def tearDown(self) -> None:
        settings.rbac_mode = self._orig_rbac_mode
        ingestion_service.get_embedding_client = self._orig_get_embedding_client

    def test_connector_reingest_preserves_existing_synced_acl(self) -> None:
        db = self.SessionLocal()
        try:
            org = Organization(
                name="ACL Org",
                slug=f"acl-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="ACL Workspace")
            db.add(workspace)
            db.flush()
            connector = IntegrationConnector(
                organization_id=org.id,
                connector_type="google-drive",
                nango_connection_id="conn-acl",
                status="active",
            )
            db.add(connector)
            db.flush()
            document = Document(
                organization_id=org.id,
                workspace_id=workspace.id,
                filename="drive-doc.txt",
                content_type="text/plain",
                storage_path="inline://google-drive/file-1",
                source_type="google-drive",
                external_id="file-1",
                status="indexed",
                integration_connector_id=connector.id,
            )
            db.add(document)
            db.flush()
            allowed_user_id = uuid4()
            db.add(
                DocumentPermission(
                    document_id=document.id,
                    organization_id=org.id,
                    user_id=allowed_user_id,
                    can_read=True,
                    source="google-drive",
                    external_id=f"file-1:user:{allowed_user_id}",
                    connector_id=str(connector.id),
                )
            )
            db.commit()

            ingest_document(
                db,
                IngestDocumentParams(
                    content="Updated connector content",
                    name="drive-doc.txt",
                    source_type="google-drive",
                    external_id="file-1",
                    organization_id=org.id,
                    workspace_id=workspace.id,
                    integration_connector_id=connector.id,
                    permission_user_ids=None,
                ),
            )

            permissions = db.query(DocumentPermission).filter(DocumentPermission.document_id == document.id).all()
            self.assertEqual(len(permissions), 1)
            self.assertEqual(permissions[0].user_id, allowed_user_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
