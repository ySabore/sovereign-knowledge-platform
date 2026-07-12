from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

import scripts.backfill_storage_metadata as backfill_module
from app.models import Document
from app.services.storage import StorageWriteResult


class _ScalarResult:
    def __init__(self, rows: list[Document]) -> None:
        self.rows = rows

    def all(self) -> list[Document]:
        return self.rows


class _FakeSession:
    def __init__(self, rows: list[Document], *, fail_commit: bool = False) -> None:
        self.rows = rows
        self.fail_commit = fail_commit
        self.committed = False
        self.closed = False
        self.rollback_count = 0
        self.expire_count = 0

    def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self.rows)

    def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.committed = True

    def rollback(self) -> None:
        self.rollback_count += 1

    def expire_all(self) -> None:
        self.expire_count += 1

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.uploaded_paths: list[Path] = []
        self.deleted_uris: list[str] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: object,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.uploaded_paths.append(local_path)
        key = f"{workspace_id}/{safe_name}"
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{key}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=key,
            etag="etag",
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        self.deleted_uris.append(storage_uri)


class StorageBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_session_local = backfill_module.SessionLocal
        self._original_get_storage_backend = backfill_module.get_storage_backend

    def tearDown(self) -> None:
        backfill_module.SessionLocal = self._original_session_local
        backfill_module.get_storage_backend = self._original_get_storage_backend

    def _document(self, storage_path: str) -> Document:
        return Document(
            organization_id=uuid4(),
            workspace_id=uuid4(),
            filename="source.pdf",
            content_type="application/pdf",
            storage_path=storage_path,
            checksum_sha256="abc123",
            source_type="file-upload",
            status="indexed",
        )

    def test_dry_run_upload_local_to_s3_has_no_external_side_effects(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "source.pdf"
            source_path.write_bytes(b"pdf")
            doc = self._document(str(source_path))
            session = _FakeSession([doc])
            backend = S3Storage()
            backfill_module.SessionLocal = lambda: session
            backfill_module.get_storage_backend = lambda: backend

            scanned, updated = backfill_module.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual((scanned, updated), (1, 1))
            self.assertTrue(source_path.is_file())
            self.assertEqual(backend.uploaded_paths, [])
            self.assertEqual(backend.deleted_uris, [])
            self.assertFalse(session.committed)
            self.assertEqual(session.rollback_count, 1)
            self.assertEqual(session.expire_count, 1)
            self.assertEqual(doc.storage_path, str(source_path))

    def test_apply_keeps_local_file_and_cleans_uploaded_object_when_commit_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "source.pdf"
            source_path.write_bytes(b"pdf")
            doc = self._document(str(source_path))
            session = _FakeSession([doc], fail_commit=True)
            backend = S3Storage()
            backfill_module.SessionLocal = lambda: session
            backfill_module.get_storage_backend = lambda: backend

            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                backfill_module.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertTrue(source_path.is_file())
            self.assertEqual(backend.uploaded_paths, [source_path])
            self.assertEqual(backend.deleted_uris, [doc.storage_path])
            self.assertEqual(session.rollback_count, 1)

    def test_apply_removes_local_file_after_successful_commit(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "source.pdf"
            source_path.write_bytes(b"pdf")
            doc = self._document(str(source_path))
            session = _FakeSession([doc])
            backend = S3Storage()
            backfill_module.SessionLocal = lambda: session
            backfill_module.get_storage_backend = lambda: backend

            scanned, updated = backfill_module.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual((scanned, updated), (1, 1))
            self.assertTrue(session.committed)
            self.assertFalse(source_path.exists())
            self.assertEqual(backend.deleted_uris, [])
            self.assertEqual(doc.storage_provider, "s3")
            self.assertEqual(doc.storage_bucket, "bucket")
            self.assertEqual(doc.storage_key, f"{doc.workspace_id}/source.pdf")


if __name__ == "__main__":
    unittest.main()
