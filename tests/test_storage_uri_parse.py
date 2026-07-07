from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services import storage as storage_service
from app.services.storage import StorageWriteResult, parse_storage_uri
from scripts import backfill_storage_metadata


class StorageUriParseTests(unittest.TestCase):
    def test_parse_s3_uri(self) -> None:
        parsed = parse_storage_uri("s3://my-bucket/a/b/file.pdf")
        self.assertEqual(parsed.provider, "s3")
        self.assertEqual(parsed.bucket, "my-bucket")
        self.assertEqual(parsed.key, "a/b/file.pdf")

    def test_parse_local_plain_path(self) -> None:
        parsed = parse_storage_uri("C:/data/documents/abc.pdf")
        self.assertEqual(parsed.provider, "local")
        self.assertIsNone(parsed.bucket)
        self.assertEqual(parsed.key, "C:/data/documents/abc.pdf")

    def test_parse_empty_uri(self) -> None:
        parsed = parse_storage_uri("")
        self.assertIsNone(parsed.provider)
        self.assertIsNone(parsed.bucket)
        self.assertIsNone(parsed.key)

    def test_delete_storage_uri_deletes_plain_local_path_without_s3_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.pdf"
            path.write_bytes(b"artifact")

            with patch.object(storage_service, "S3Storage", side_effect=AssertionError("S3 should not be used")):
                storage_service.delete_storage_uri(str(path))

            self.assertFalse(path.exists())

    def test_delete_storage_uri_dispatches_s3_uri_to_s3_backend(self) -> None:
        deleted: list[str] = []

        class FakeS3Storage:
            def delete_by_uri(self, storage_uri: str) -> None:
                deleted.append(storage_uri)

        with patch.object(storage_service, "S3Storage", FakeS3Storage):
            storage_service.delete_storage_uri("s3://bucket/key.pdf")

        self.assertEqual(deleted, ["s3://bucket/key.pdf"])


class _FakeScalarResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace], *, commit_error: Exception | None = None) -> None:
        self.rows = rows
        self.commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0
        self.expire_all_calls = 0
        self.closed = False

    def scalars(self, _statement: object) -> _FakeScalarResult:
        return _FakeScalarResult(self.rows)

    def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        self.expire_all_calls += 1

    def close(self) -> None:
        self.closed = True


def _document(storage_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=storage_path,
        storage_provider=None,
        storage_bucket=None,
        storage_key=None,
        storage_size_bytes=None,
        storage_etag=None,
        workspace_id=uuid4(),
        filename="doc.pdf",
        checksum_sha256="abc123",
    )


class S3Storage:
    def __init__(self) -> None:
        self.store_calls = 0
        self.deleted: list[str] = []

    def store_upload(self, **_kwargs: object) -> StorageWriteResult:
        self.store_calls += 1
        return StorageWriteResult(
            storage_uri="s3://bucket/migrated/doc.pdf",
            extraction_path=str(_kwargs["local_path"]),
            checksum_sha256="abc123",
            size_bytes=8,
            provider="s3",
            bucket="bucket",
            key="migrated/doc.pdf",
            etag="etag",
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        self.deleted.append(storage_uri)


class StorageBackfillTests(unittest.TestCase):
    def test_upload_to_s3_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "doc.pdf"
            local_path.write_bytes(b"artifact")
            doc = _document(str(local_path))
            db = _FakeSession([doc])
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.store_calls, 0)
            self.assertTrue(local_path.exists())
            self.assertEqual(db.rollbacks, 1)
            self.assertEqual(db.expire_all_calls, 1)
            self.assertTrue(db.closed)

    def test_upload_to_s3_commit_failure_keeps_local_file_and_deletes_uploaded_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "doc.pdf"
            local_path.write_bytes(b"artifact")
            doc = _document(str(local_path))
            db = _FakeSession([doc], commit_error=RuntimeError("commit failed"))
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(backend.store_calls, 1)
            self.assertEqual(backend.deleted, ["s3://bucket/migrated/doc.pdf"])
            self.assertTrue(local_path.exists())
            self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()

