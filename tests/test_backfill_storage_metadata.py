from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class _ScalarRows:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self.rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.rollback_count = 0
        self.commit_count = 0
        self.closed = False

    def scalars(self, _stmt: object) -> _ScalarRows:
        return _ScalarRows(self.rows)

    def rollback(self) -> None:
        self.rollback_count += 1

    def expire_all(self) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1

    def close(self) -> None:
        self.closed = True


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
            storage_uri=f"s3://bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=f"{workspace_id}/{safe_name}",
        )


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_upload_local_to_s3_does_not_upload_or_delete(self) -> None:
        original_session_local = backfill_storage_metadata.SessionLocal
        original_get_storage_backend = backfill_storage_metadata.get_storage_backend

        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "case.txt"
            local_path.write_text("important", encoding="utf-8")
            doc = SimpleNamespace(
                storage_path=str(local_path),
                storage_provider="local",
                storage_bucket=None,
                storage_key=str(local_path),
                storage_size_bytes=local_path.stat().st_size,
                storage_etag=None,
                workspace_id=uuid4(),
                filename="case.txt",
                checksum_sha256="abc123",
            )
            session = _FakeSession([doc])
            backend = S3Storage()

            try:
                backfill_storage_metadata.SessionLocal = lambda: session
                backfill_storage_metadata.get_storage_backend = lambda: backend

                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )
            finally:
                backfill_storage_metadata.SessionLocal = original_session_local
                backfill_storage_metadata.get_storage_backend = original_get_storage_backend

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.uploads, [])
            self.assertTrue(local_path.is_file())
            self.assertEqual(doc.storage_path, str(local_path))
            self.assertEqual(session.rollback_count, 1)
            self.assertEqual(session.commit_count, 0)
            self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
