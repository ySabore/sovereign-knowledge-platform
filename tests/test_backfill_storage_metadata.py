from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from scripts import backfill_storage_metadata


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[object], path_that_must_exist_at_commit: Path | None = None) -> None:
        self.rows = rows
        self.path_that_must_exist_at_commit = path_that_must_exist_at_commit
        self.committed = False
        self.closed = False
        self.rollbacks = 0

    def scalars(self, _query: object) -> _ScalarResult:
        return _ScalarResult(self.rows)

    def commit(self) -> None:
        if self.path_that_must_exist_at_commit is not None:
            assert self.path_that_must_exist_at_commit.is_file()
        self.committed = True

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.uploads: list[Path] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: object,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> SimpleNamespace:
        self.uploads.append(local_path)
        return SimpleNamespace(
            storage_uri=f"s3://bucket/documents/{safe_name}",
            provider="s3",
            bucket="bucket",
            key=f"documents/{safe_name}",
            etag="etag",
            size_bytes=size_bytes,
        )


class BackfillStorageMetadataTests(unittest.TestCase):
    def _doc_for_path(self, path: Path) -> SimpleNamespace:
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

    def test_local_file_is_deleted_only_after_successful_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_file = Path(tmp) / "doc.txt"
            local_file.write_text("important", encoding="utf-8")
            doc = self._doc_for_path(local_file)
            db = _FakeDb([doc], path_that_must_exist_at_commit=local_file)
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=True,
                    upload_local_to_s3=True,
                )

            self.assertEqual((1, 1), (scanned, updated))
            self.assertTrue(db.committed)
            self.assertFalse(local_file.exists())
            self.assertEqual(str(doc.storage_path), "s3://bucket/documents/doc.txt")
            self.assertEqual([local_file], backend.uploads)

    def test_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_file = Path(tmp) / "doc.txt"
            local_file.write_text("important", encoding="utf-8")
            doc = self._doc_for_path(local_file)
            db = _FakeDb([doc])
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual((1, 1), (scanned, updated))
            self.assertFalse(db.committed)
            self.assertTrue(local_file.is_file())
            self.assertEqual([], backend.uploads)


if __name__ == "__main__":
    unittest.main()
