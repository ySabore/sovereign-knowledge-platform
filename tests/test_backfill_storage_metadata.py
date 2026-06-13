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
            storage_uri=f"s3://artifact-bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="artifact-bucket",
            key=f"{workspace_id}/{safe_name}",
            etag="etag",
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

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_document(self, storage_path: Path) -> tuple:
        db = self.SessionLocal()
        try:
            org = Organization(
                name="Storage Backfill Org",
                slug=f"storage-backfill-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Backfill Workspace")
            db.add(workspace)
            db.flush()
            doc = Document(
                organization_id=org.id,
                workspace_id=workspace.id,
                filename=storage_path.name,
                content_type="text/plain",
                storage_path=str(storage_path),
                source_type="file-upload",
            )
            db.add(doc)
            db.commit()
            return doc.id, workspace.id
        finally:
            db.close()

    def _document(self, doc_id):
        db = self.SessionLocal()
        try:
            return db.get(Document, doc_id)
        finally:
            db.close()

    def test_upload_dry_run_does_not_upload_or_delete_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "source.txt"
            local_path.write_text("important artifact", encoding="utf-8")
            doc_id, _ = self._seed_document(local_path)
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", self.SessionLocal),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.uploads, [])
            self.assertTrue(local_path.is_file())
            self.assertEqual(self._document(doc_id).storage_path, str(local_path))

    def test_failed_commit_keeps_local_artifact_after_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "source.txt"
            local_path.write_text("important artifact", encoding="utf-8")
            doc_id, _ = self._seed_document(local_path)
            backend = S3Storage()

            def failing_session_factory():
                session = self.SessionLocal()

                def fail_commit() -> None:
                    raise RuntimeError("database commit failed")

                session.commit = fail_commit
                return session

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", failing_session_factory),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                with self.assertRaises(RuntimeError):
                    backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(len(backend.uploads), 1)
            self.assertTrue(local_path.is_file())
            self.assertEqual(self._document(doc_id).storage_path, str(local_path))


if __name__ == "__main__":
    unittest.main()
