from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("AUDIT_HTTP_MIDDLEWARE_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    Organization,
    OrganizationMembership,
    OrgMembershipRole,
    OrgStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.services.ingestion_service import IngestDocumentParams, ingest_document


class IngestTextUploadGuardTests(unittest.TestCase):
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
            user = User(
                email="ingest-guard@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Ingest Guard Editor",
                is_active=True,
                is_platform_owner=False,
            )
            db.add(user)
            db.flush()
            self.user_id = user.id

            org = Organization(
                name="Ingest Guard Org",
                slug=f"ingest-guard-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            self.org_id = org.id

            workspace = Workspace(organization_id=org.id, name="General", description="Guard workspace")
            db.add(workspace)
            db.flush()
            self.workspace_id = workspace.id

            db.add(
                OrganizationMembership(
                    user_id=user.id,
                    organization_id=org.id,
                    role=OrgMembershipRole.member.value,
                )
            )
            db.add(
                WorkspaceMember(
                    user_id=user.id,
                    workspace_id=workspace.id,
                    role=WorkspaceMemberRole.editor.value,
                )
            )

            document = Document(
                organization_id=org.id,
                workspace_id=workspace.id,
                created_by=user.id,
                filename="policy.pdf",
                content_type="application/pdf",
                storage_path="/tmp/data/documents/policy.pdf",
                storage_provider="local",
                storage_bucket=None,
                storage_key="/tmp/data/documents/policy.pdf",
                checksum_sha256="abc123",
                source_type="pdf-upload",
                status=DocumentStatus.indexed.value,
            )
            db.add(document)
            db.flush()
            document.external_id = str(document.id)
            self.document_id = document.id

            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=1,
                    section_title=None,
                    content="Original uploaded policy text that must not be replaced.",
                    token_count=48,
                    embedding_model="test-embed",
                    embedding=[0.1, 0.2, 0.3],
                )
            )
            db.commit()
        finally:
            db.close()

    def _login(self) -> dict[str, str]:
        resp = self.client.post(
            "/auth/login",
            json={"email": "ingest-guard@example.com", "password": "ChangeMeNow!"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_ingest_text_rejects_reserved_upload_source_type(self) -> None:
        headers = self._login()
        resp = self.client.post(
            f"/documents/workspaces/{self.workspace_id}/ingest-text",
            headers=headers,
            json={
                "content": "Attacker controlled replacement content for RAG.",
                "name": "poison.pdf",
                "source_type": "pdf-upload",
                "external_id": str(self.document_id),
            },
        )
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("reserved for file uploads", resp.text)

        db = self.SessionLocal()
        try:
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == self.document_id)
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            self.assertEqual(len(chunks), 1)
            self.assertIn("Original uploaded policy text", chunks[0].content)
            doc = db.get(Document, self.document_id)
            assert doc is not None
            self.assertEqual(doc.filename, "policy.pdf")
            self.assertEqual(doc.checksum_sha256, "abc123")
        finally:
            db.close()

    def test_ingest_document_refuses_to_replace_upload_chunks(self) -> None:
        db = self.SessionLocal()
        try:
            with self.assertRaises(ValueError) as ctx:
                ingest_document(
                    db,
                    IngestDocumentParams(
                        content="Attacker controlled replacement content for RAG.",
                        name="poison.pdf",
                        source_type="pdf-upload",
                        external_id=str(self.document_id),
                        organization_id=self.org_id,
                        workspace_id=self.workspace_id,
                        created_by=self.user_id,
                    ),
                )
            self.assertIn("file-upload document", str(ctx.exception))

            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == self.document_id)
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            self.assertEqual(len(chunks), 1)
            self.assertIn("Original uploaded policy text", chunks[0].content)
        finally:
            db.close()

    def test_ingest_text_still_allows_connector_source_types(self) -> None:
        headers = self._login()

        class _FakeEmbedClient:
            def embed_texts_batched(self, texts):
                return [[0.01] * 8 for _ in texts]

        with patch("app.services.ingestion_service.get_embedding_client", return_value=_FakeEmbedClient()):
            resp = self.client.post(
                f"/documents/workspaces/{self.workspace_id}/ingest-text",
                headers=headers,
                json={
                    "content": "Confluence page body that should index normally.",
                    "name": "Runbook",
                    "source_type": "confluence",
                    "external_id": "page-123",
                },
            )
        self.assertEqual(resp.status_code, 201, resp.text)
        payload = resp.json()
        self.assertEqual(payload["chunks_created"], 1)
        self.assertNotEqual(payload["document_id"], str(self.document_id))


if __name__ == "__main__":
    unittest.main()
