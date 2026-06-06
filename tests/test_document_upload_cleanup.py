from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models import Organization, OrganizationMembership, OrgMembershipRole, OrgStatus, User, Workspace, WorkspaceMember, WorkspaceMemberRole
from app.services.ingestion import StoredUpload


class DocumentUploadCleanupTests(unittest.TestCase):
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
            user = User(
                email="upload-cleanup@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Upload Cleanup",
                is_active=True,
                is_platform_owner=False,
            )
            db.add(user)
            db.flush()
            org = Organization(
                name="Upload Cleanup Org",
                slug=f"upload-cleanup-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Upload Cleanup Workspace")
            db.add(workspace)
            db.flush()
            db.add_all(
                [
                    OrganizationMembership(
                        user_id=user.id,
                        organization_id=org.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    WorkspaceMember(
                        user_id=user.id,
                        workspace_id=workspace.id,
                        role=WorkspaceMemberRole.editor.value,
                    ),
                ]
            )
            db.commit()
            self.workspace_id = workspace.id
        finally:
            db.close()

    def _login(self) -> dict[str, str]:
        resp = self.client.post("/auth/login", json={"email": "upload-cleanup@example.com", "password": "ChangeMeNow!"})
        self.assertEqual(resp.status_code, 200, resp.text)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_failed_document_upload_removes_stored_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "stored.txt"
            artifact.write_text("stored before extraction", encoding="utf-8")
            stored = StoredUpload(
                storage_path=str(artifact),
                extraction_path=str(artifact),
                checksum_sha256="abc123",
                size_bytes=artifact.stat().st_size,
                storage_provider="local",
                storage_key=str(artifact),
            )

            with patch("app.routers.documents.persist_upload_file", new=AsyncMock(return_value=stored)), patch(
                "app.routers.documents.extract_pages_from_upload", return_value=[]
            ):
                resp = self.client.post(
                    f"/documents/workspaces/{self.workspace_id}/upload",
                    headers=self._login(),
                    files={"file": ("stored.txt", b"hello", "text/plain")},
                )

            self.assertEqual(resp.status_code, 422, resp.text)
            self.assertFalse(artifact.exists())


if __name__ == "__main__":
    unittest.main()
