from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata as bsm


class _ScalarRows:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace], *, fail_commit: bool = False) -> None:
        self._rows = rows
        self.fail_commit = fail_commit
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def scalars(self, _statement: object) -> _ScalarRows:
        return _ScalarRows(self._rows)

    def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _local_doc(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider="local",
        storage_bucket=None,
        storage_key=str(path),
        storage_size_bytes=path.stat().st_size,
        storage_etag=None,
        checksum_sha256="abc123",
        workspace_id=uuid4(),
        filename=path.name,
    )


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_upload_local_to_s3_does_not_touch_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "doc.txt"
            local_path.write_text("hello", encoding="utf-8")
            doc = _local_doc(local_path)
            session = _FakeSession([doc])

            class S3Storage:
                def store_upload(self, **_kwargs: object) -> StorageWriteResult:
                    raise AssertionError("dry-run must not upload to S3")

            with (
                patch.object(bsm, "SessionLocal", return_value=session),
                patch.object(bsm, "get_storage_backend", return_value=S3Storage()),
            ):
                scanned, updated = bsm.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual((scanned, updated), (1, 1))
            self.assertTrue(local_path.is_file())
            self.assertEqual(doc.storage_path, str(local_path))
            self.assertEqual(session.commits, 0)

    def test_apply_keeps_local_file_when_database_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "doc.txt"
            local_path.write_text("hello", encoding="utf-8")
            doc = _local_doc(local_path)
            session = _FakeSession([doc], fail_commit=True)
            uploads: list[Path] = []

            class S3Storage:
                def store_upload(
                    self,
                    *,
                    local_path: Path,
                    workspace_id: object,
                    safe_name: str,
                    checksum_sha256: str,
                    size_bytes: int,
                ) -> StorageWriteResult:
                    uploads.append(local_path)
                    return StorageWriteResult(
                        storage_uri=f"s3://bucket/documents/{safe_name}",
                        extraction_path=str(local_path),
                        checksum_sha256=checksum_sha256,
                        size_bytes=size_bytes,
                        provider="s3",
                        bucket="bucket",
                        key=f"documents/{safe_name}",
                        etag="etag",
                    )

            with (
                patch.object(bsm, "SessionLocal", return_value=session),
                patch.object(bsm, "get_storage_backend", return_value=S3Storage()),
            ):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    bsm.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(uploads, [local_path])
            self.assertTrue(local_path.is_file())
            self.assertEqual(session.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
