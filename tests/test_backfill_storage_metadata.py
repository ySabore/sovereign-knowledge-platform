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
from app.models import Document, Organization, Workspace
from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class S3Storage:
    def __init__(self) -> None:
        self.uploads: list[Path] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.uploads.append(local_path)
        return StorageWriteResult(
            storage_uri=f"s3://archive-bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="archive-bucket",
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
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.tmp.cleanup()

    def _seed_document(self, storage_path: Path) -> tuple[str, str]:
        db = self.SessionLocal()
        try:
            org = Organization(
                name="Backfill Org",
                slug=f"backfill-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Backfill Workspace")
            db.add(workspace)
            db.flush()
            document = Document(
                organization_id=org.id,
                workspace_id=workspace.id,
                filename=storage_path.name,
                content_type="text/plain",
                storage_path=str(storage_path),
                source_type="file-upload",
                external_id=str(uuid4()),
                status="indexed",
                page_count=1,
            )
            db.add(document)
            db.commit()
            return str(document.id), str(document.storage_path)
        finally:
            db.close()

    def _get_document(self, document_id: str) -> Document:
        db = self.SessionLocal()
        try:
            document = db.get(Document, document_id)
            self.assertIsNotNone(document)
            db.expunge(document)
            return document
        finally:
            db.close()

    def test_dry_run_upload_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        artifact = Path(self.tmp.name) / "artifact.txt"
        artifact.write_text("important bytes", encoding="utf-8")
        document_id, original_path = self._seed_document(artifact)
        backend = S3Storage()

        with (
            patch.object(backfill_storage_metadata, "SessionLocal", self.SessionLocal),
            patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
        ):
            scanned, updated = backfill_storage_metadata.backfill(apply_changes=False, upload_local_to_s3=True)

        self.assertEqual(scanned, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(backend.uploads, [])
        self.assertTrue(artifact.is_file())
        document = self._get_document(document_id)
        self.assertEqual(document.storage_path, original_path)
        self.assertIsNone(document.storage_provider)

    def test_apply_commits_s3_metadata_before_removing_local_file(self) -> None:
        artifact = Path(self.tmp.name) / "artifact.txt"
        artifact.write_text("important bytes", encoding="utf-8")
        document_id, _ = self._seed_document(artifact)
        backend = S3Storage()

        with (
            patch.object(backfill_storage_metadata, "SessionLocal", self.SessionLocal),
            patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            patch.object(Path, "unlink", side_effect=OSError("local file is locked")),
        ):
            with self.assertRaises(OSError):
                backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

        document = self._get_document(document_id)
        self.assertEqual(document.storage_path, f"s3://archive-bucket/{document.workspace_id}/artifact.txt")
        self.assertEqual(document.storage_provider, "s3")
        self.assertEqual(document.storage_bucket, "archive-bucket")
        self.assertTrue(artifact.is_file())


if __name__ == "__main__":
    unittest.main()
