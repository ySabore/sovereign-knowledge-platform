from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.storage import StorageWriteResult, delete_storage_uri
from scripts import backfill_storage_metadata


class _Rows:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace], *, fail_commit: bool = False) -> None:
        self._rows = rows
        self.fail_commit = fail_commit
        self.committed = False
        self.rollbacks = 0

    def scalars(self, _statement: object) -> _Rows:
        return _Rows(self._rows)

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        return None

    def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.committed = True

    def close(self) -> None:
        return None


class StorageSafetyTests(unittest.TestCase):
    def _document_for_path(self, path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            storage_path=str(path),
            storage_provider=None,
            storage_bucket=None,
            storage_key=None,
            storage_etag=None,
            storage_size_bytes=None,
            workspace_id=uuid4(),
            filename="brief.pdf",
            checksum_sha256="abc123",
            created_at=None,
        )

    def test_backfill_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "brief.pdf"
            local_path.write_text("evidence", encoding="utf-8")
            doc = self._document_for_path(local_path)
            session = _FakeSession([doc])

            class S3Storage:
                uploads = 0

                def store_upload(self, **_kwargs: object) -> StorageWriteResult:
                    S3Storage.uploads += 1
                    raise AssertionError("dry-run must not upload")

            with patch.object(backfill_storage_metadata, "get_storage_backend", return_value=S3Storage()), patch.object(
                backfill_storage_metadata, "SessionLocal", return_value=session
            ):
                scanned, updated = backfill_storage_metadata.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(S3Storage.uploads, 0)
            self.assertTrue(local_path.is_file())
            self.assertEqual(session.rollbacks, 1)

    def test_backfill_keeps_local_file_when_commit_fails_after_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "brief.pdf"
            local_path.write_text("evidence", encoding="utf-8")
            doc = self._document_for_path(local_path)
            session = _FakeSession([doc], fail_commit=True)

            class S3Storage:
                def store_upload(self, **_kwargs: object) -> StorageWriteResult:
                    return StorageWriteResult(
                        storage_uri="s3://archive/ws/brief.pdf",
                        extraction_path=str(local_path),
                        checksum_sha256="abc123",
                        size_bytes=local_path.stat().st_size,
                        provider="s3",
                        bucket="archive",
                        key="ws/brief.pdf",
                    )

            with patch.object(backfill_storage_metadata, "get_storage_backend", return_value=S3Storage()), patch.object(
                backfill_storage_metadata, "SessionLocal", return_value=session
            ):
                with self.assertRaises(RuntimeError):
                    backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertTrue(local_path.is_file())

    def test_delete_storage_uri_deletes_s3_uri_without_configured_bucket(self) -> None:
        calls: list[tuple[str, str]] = []

        class FakeS3Client:
            def delete_object(self, *, Bucket: str, Key: str) -> None:
                calls.append((Bucket, Key))

        fake_boto3 = SimpleNamespace(client=lambda *_args, **_kwargs: FakeS3Client())
        with patch.dict(sys.modules, {"boto3": fake_boto3}), patch("app.services.storage.settings.s3_bucket", ""):
            delete_storage_uri("s3://archive/workspace/brief.pdf")

        self.assertEqual(calls, [("archive", "workspace/brief.pdf")])

    def test_delete_storage_uri_deletes_local_path_without_current_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "brief.pdf"
            local_path.write_text("evidence", encoding="utf-8")

            delete_storage_uri(str(local_path))

            self.assertFalse(local_path.exists())


if __name__ == "__main__":
    unittest.main()
