from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class _ScalarResult:
    def __init__(self, docs: list[SimpleNamespace]) -> None:
        self._docs = docs

    def all(self) -> list[SimpleNamespace]:
        return self._docs


class _FakeSession:
    def __init__(self, docs: list[SimpleNamespace], *, commit_error: Exception | None = None) -> None:
        self._docs = docs
        self._commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0
        self.expire_calls = 0
        self.closed = False

    def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self._docs)

    def commit(self) -> None:
        self.commits += 1
        if self._commit_error is not None:
            raise self._commit_error

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        self.expire_calls += 1

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.uploaded_paths: list[Path] = []

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
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=f"{workspace_id}/{safe_name}",
            etag="etag",
        )


def _document_for(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider="local",
        storage_bucket=None,
        storage_key=str(path),
        storage_size_bytes=path.stat().st_size,
        storage_etag=None,
        workspace_id=uuid4(),
        filename=path.name,
        checksum_sha256="checksum",
    )


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_upload_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "document.pdf"
            local_path.write_bytes(b"pdf")
            doc = _document_for(local_path)
            db = _FakeSession([doc])
            backend = S3Storage()

            with (
                mock.patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                mock.patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.uploaded_paths, [])
            self.assertTrue(local_path.is_file())
            self.assertEqual(doc.storage_path, str(local_path))
            self.assertEqual(db.rollbacks, 1)
            self.assertEqual(db.expire_calls, 1)
            self.assertEqual(db.commits, 0)
            self.assertTrue(db.closed)

    def test_apply_upload_to_s3_keeps_local_file_when_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "document.pdf"
            local_path.write_bytes(b"pdf")
            db = _FakeSession([_document_for(local_path)], commit_error=RuntimeError("commit failed"))
            backend = S3Storage()

            with (
                mock.patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                mock.patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(backend.uploaded_paths, [local_path])
            self.assertTrue(local_path.is_file())
            self.assertEqual(db.commits, 1)
            self.assertEqual(db.rollbacks, 1)
            self.assertTrue(db.closed)

    def test_apply_upload_to_s3_deletes_local_file_after_successful_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "document.pdf"
            local_path.write_bytes(b"pdf")
            doc = _document_for(local_path)
            db = _FakeSession([doc])
            backend = S3Storage()

            with (
                mock.patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                mock.patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=True,
                    upload_local_to_s3=True,
                )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.uploaded_paths, [local_path])
            self.assertFalse(local_path.exists())
            self.assertEqual(doc.storage_path, f"s3://bucket/{doc.workspace_id}/document.pdf")
            self.assertEqual(doc.storage_provider, "s3")
            self.assertEqual(db.commits, 1)
            self.assertEqual(db.rollbacks, 0)
            self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
