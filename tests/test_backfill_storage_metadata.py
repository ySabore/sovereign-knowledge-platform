from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from scripts import backfill_storage_metadata


class _FakeScalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def scalars(self, _statement: object) -> _FakeScalars:
        return _FakeScalars(self._rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.store_calls = 0

    def store_upload(self, **_kwargs: object) -> object:
        self.store_calls += 1
        return SimpleNamespace(
            storage_uri="s3://bucket/workspace/file.txt",
            provider="s3",
            bucket="bucket",
            key="workspace/file.txt",
            etag="etag",
            size_bytes=12,
        )


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_upload_local_to_s3_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "file.txt"
            local_path.write_text("hello world!", encoding="utf-8")
            doc = SimpleNamespace(
                storage_path=str(local_path),
                storage_provider=None,
                storage_bucket=None,
                storage_key=None,
                storage_size_bytes=None,
                storage_etag=None,
                workspace_id=uuid4(),
                filename="file.txt",
                checksum_sha256="abc123",
            )
            db = _FakeDb([doc])
            backend = S3Storage()

            with patch.object(backfill_storage_metadata, "SessionLocal", return_value=db), patch.object(
                backfill_storage_metadata, "get_storage_backend", return_value=backend
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.store_calls, 0)
            self.assertTrue(local_path.is_file())
            self.assertEqual(db.commits, 0)
            self.assertEqual(db.rollbacks, 1)
            self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
