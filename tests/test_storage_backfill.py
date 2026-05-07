from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from scripts import backfill_storage_metadata


class _ScalarRows:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[SimpleNamespace], *, fail_commit: bool = False) -> None:
        self.rows = rows
        self.fail_commit = fail_commit
        self.commits = 0
        self.rollbacks = 0
        self.expirations = 0
        self.closed = False

    def scalars(self, _stmt: object) -> _ScalarRows:
        return _ScalarRows(self.rows)

    def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        self.expirations += 1

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.uploads = 0

    def store_upload(self, **_kwargs: object) -> SimpleNamespace:
        self.uploads += 1
        return SimpleNamespace(
            storage_uri="s3://bucket/documents/file.txt",
            provider="s3",
            bucket="bucket",
            key="documents/file.txt",
            etag="etag",
            size_bytes=12,
        )


def _doc_for(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider=None,
        storage_bucket=None,
        storage_key=None,
        storage_size_bytes=None,
        storage_etag=None,
        workspace_id=uuid4(),
        filename=path.name,
        checksum_sha256="abc123",
    )


class StorageBackfillTests(unittest.TestCase):
    def test_dry_run_upload_local_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_text("hello", encoding="utf-8")
            db = _FakeDb([_doc_for(path)])
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
            self.assertEqual(backend.uploads, 0)
            self.assertTrue(path.exists())
            self.assertEqual(db.commits, 0)
            self.assertEqual(db.rollbacks, 1)
            self.assertTrue(db.closed)

    def test_apply_migration_keeps_local_file_when_db_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_text("hello", encoding="utf-8")
            db = _FakeDb([_doc_for(path)], fail_commit=True)
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                with self.assertRaises(RuntimeError):
                    backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(backend.uploads, 1)
            self.assertTrue(path.exists())
            self.assertEqual(db.commits, 1)
            self.assertEqual(db.rollbacks, 1)
            self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
