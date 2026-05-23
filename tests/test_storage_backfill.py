from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, DocumentStatus, OrgStatus, Organization, Workspace
from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class S3Storage:
    def __init__(self) -> None:
        self.uploaded_paths: list[Path] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.uploaded_paths.append(local_path)
        return StorageWriteResult(
            storage_uri=f"s3://bucket/documents/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=f"documents/{workspace_id}/{safe_name}",
            etag="etag",
        )


class StorageBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.original_session_local = backfill_storage_metadata.SessionLocal
        self.original_get_storage_backend = backfill_storage_metadata.get_storage_backend
        backfill_storage_metadata.SessionLocal = self.SessionLocal
        self.backend = S3Storage()
        backfill_storage_metadata.get_storage_backend = lambda: self.backend

    def tearDown(self) -> None:
        backfill_storage_metadata.SessionLocal = self.original_session_local
        backfill_storage_metadata.get_storage_backend = self.original_get_storage_backend
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _create_local_document(self, storage_path: str, size_bytes: int) -> None:
        db = self.SessionLocal()
        try:
            org = Organization(
                name="Storage Org",
                slug=f"storage-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Storage Workspace")
            db.add(workspace)
            db.flush()
            db.add(
                Document(
                    organization_id=org.id,
                    workspace_id=workspace.id,
                    filename="local.txt",
                    content_type="text/plain",
                    storage_path=storage_path,
                    storage_provider="local",
                    storage_bucket=None,
                    storage_key=storage_path,
                    storage_size_bytes=size_bytes,
                    checksum_sha256="abc123",
                    source_type="file-upload",
                    external_id=str(uuid4()),
                    status=DocumentStatus.indexed.value,
                    page_count=1,
                )
            )
            db.commit()
        finally:
            db.close()

    def test_dry_run_upload_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "local.txt"
            payload = b"critical document"
            local_path.write_bytes(payload)
            self._create_local_document(str(local_path), len(payload))

            scanned, updated = backfill_storage_metadata.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(self.backend.uploaded_paths, [])
            self.assertTrue(local_path.exists())
            db = self.SessionLocal()
            try:
                doc = db.query(Document).one()
                self.assertEqual(doc.storage_path, str(local_path))
                self.assertEqual(doc.storage_provider, "local")
            finally:
                db.close()

    def test_apply_upload_to_s3_removes_local_file_after_db_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "local.txt"
            payload = b"critical document"
            local_path.write_bytes(payload)
            self._create_local_document(str(local_path), len(payload))

            scanned, updated = backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(self.backend.uploaded_paths, [local_path])
            self.assertFalse(local_path.exists())
            db = self.SessionLocal()
            try:
                doc = db.query(Document).one()
                self.assertEqual(doc.storage_provider, "s3")
                self.assertEqual(doc.storage_bucket, "bucket")
                self.assertEqual(doc.storage_path, f"s3://bucket/documents/{doc.workspace_id}/local.txt")
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
