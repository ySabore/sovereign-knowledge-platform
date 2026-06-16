from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document
from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class S3Storage:
    def __init__(self) -> None:
        self.store_calls = 0

    def store_upload(self, *, local_path: Path, workspace_id, safe_name: str, checksum_sha256: str, size_bytes: int):
        self.store_calls += 1
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=f"{workspace_id}/{safe_name}",
        )


class StorageBackfillSafetyTests(unittest.TestCase):
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
        self._orig_session_local = backfill_storage_metadata.SessionLocal
        self._orig_get_storage_backend = backfill_storage_metadata.get_storage_backend
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        backfill_storage_metadata.SessionLocal = self._orig_session_local
        backfill_storage_metadata.get_storage_backend = self._orig_get_storage_backend
        self.tmpdir.cleanup()

    def _insert_document(self, local_path: Path) -> Document:
        db = self.SessionLocal()
        try:
            doc = Document(
                organization_id=uuid4(),
                workspace_id=uuid4(),
                created_by=None,
                filename=local_path.name,
                content_type="text/plain",
                storage_path=str(local_path),
                checksum_sha256="abc123",
                source_type="file-upload",
                external_id=str(uuid4()),
                status="indexed",
                page_count=1,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc
        finally:
            db.close()

    def test_dry_run_upload_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        local_path = Path(self.tmpdir.name) / "doc.txt"
        local_path.write_text("important")
        self._insert_document(local_path)
        fake_backend = S3Storage()
        backfill_storage_metadata.SessionLocal = self.SessionLocal
        backfill_storage_metadata.get_storage_backend = lambda: fake_backend

        scanned, updated = backfill_storage_metadata.backfill(apply_changes=False, upload_local_to_s3=True)

        self.assertEqual(scanned, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(fake_backend.store_calls, 0)
        self.assertTrue(local_path.exists())

    def test_apply_keeps_local_file_if_database_commit_fails(self) -> None:
        local_path = Path(self.tmpdir.name) / "doc.txt"
        local_path.write_text("important")
        self._insert_document(local_path)
        fake_backend = S3Storage()
        session = self.SessionLocal()
        session.commit = lambda: (_ for _ in ()).throw(RuntimeError("commit failed"))  # type: ignore[method-assign]
        backfill_storage_metadata.SessionLocal = lambda: session
        backfill_storage_metadata.get_storage_backend = lambda: fake_backend

        with self.assertRaises(RuntimeError):
            backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

        self.assertEqual(fake_backend.store_calls, 1)
        self.assertTrue(local_path.exists())


if __name__ == "__main__":
    unittest.main()
