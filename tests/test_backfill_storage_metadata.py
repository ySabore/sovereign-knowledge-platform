from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, Organization, OrgStatus, Workspace
from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class S3Storage:
    def __init__(self) -> None:
        self.upload_count = 0

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.upload_count += 1
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=f"{workspace_id}/{safe_name}",
        )


class BackfillStorageMetadataTests(unittest.TestCase):
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

    def _seed_document(self, storage_path: str, size_bytes: int) -> None:
        db = self.SessionLocal()
        try:
            org = Organization(
                name="Backfill Org",
                slug=f"backfill-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Backfill Workspace", description="Backfill test")
            db.add(workspace)
            db.flush()
            db.add(
                Document(
                    organization_id=org.id,
                    workspace_id=workspace.id,
                    filename="document.pdf",
                    content_type="application/pdf",
                    storage_path=storage_path,
                    storage_provider="local",
                    storage_bucket=None,
                    storage_key=storage_path,
                    storage_size_bytes=size_bytes,
                    source_type="file-upload",
                    external_id=str(uuid4()),
                    status="indexed",
                    page_count=1,
                )
            )
            db.commit()
        finally:
            db.close()

    def test_dry_run_upload_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "document.pdf"
            local_path.write_bytes(b"pdf")
            self._seed_document(str(local_path), local_path.stat().st_size)
            backend = S3Storage()

            with patch.object(backfill_storage_metadata, "SessionLocal", self.SessionLocal), patch.object(
                backfill_storage_metadata,
                "get_storage_backend",
                return_value=backend,
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.upload_count, 0)
            self.assertTrue(local_path.is_file())

            db = self.SessionLocal()
            try:
                doc = db.query(Document).one()
                self.assertEqual(doc.storage_path, str(local_path))
                self.assertEqual(doc.storage_provider, "local")
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
