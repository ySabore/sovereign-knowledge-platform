from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, Organization, OrgStatus, Workspace
from app.services.storage import StorageWriteResult
import scripts.backfill_storage_metadata as backfill_module


class S3Storage:
    def __init__(self) -> None:
        self.store_calls = 0

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.store_calls += 1
        return StorageWriteResult(
            storage_uri=f"s3://test-bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="test-bucket",
            key=f"{workspace_id}/{safe_name}",
            etag="etag-1",
        )


class BackfillStorageMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._original_session_local = backfill_module.SessionLocal
        self._original_get_storage_backend = backfill_module.get_storage_backend

    def tearDown(self) -> None:
        backfill_module.SessionLocal = self._original_session_local
        backfill_module.get_storage_backend = self._original_get_storage_backend
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_document(self, storage_path: str) -> None:
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
                    filename="document.txt",
                    content_type="text/plain",
                    storage_path=storage_path,
                    source_type="file-upload",
                    external_id=str(uuid4()),
                    status="indexed",
                    page_count=1,
                )
            )
            db.commit()
        finally:
            db.close()

    def test_dry_run_upload_local_to_s3_has_no_storage_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "document.txt"
            local_path.write_text("important data", encoding="utf-8")
            self._seed_document(str(local_path))

            backend = S3Storage()
            backfill_module.SessionLocal = self.SessionLocal
            backfill_module.get_storage_backend = lambda: backend

            scanned, updated = backfill_module.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.store_calls, 0)
            self.assertTrue(local_path.is_file())

            db = self.SessionLocal()
            try:
                doc = db.query(Document).one()
                self.assertEqual(doc.storage_path, str(local_path))
                self.assertIsNone(doc.storage_provider)
                self.assertIsNone(doc.storage_size_bytes)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
