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
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows
        self.commits = 0
        self.rollbacks = 0
        self.expire_all_calls = 0
        self.closed = False

    def scalars(self, _statement: object) -> _ScalarRows:
        return _ScalarRows(self._rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        self.expire_all_calls += 1

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
    ) -> StorageWriteResult:
        self.uploads.append(local_path)
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=safe_name,
        )


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_upload_local_to_s3_has_no_storage_side_effects(self) -> None:
        original_session_local = backfill_storage_metadata.SessionLocal
        original_get_storage_backend = backfill_storage_metadata.get_storage_backend

        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "contract.pdf"
            local_path.write_bytes(b"important document")
            doc = SimpleNamespace(
                storage_path=str(local_path),
                storage_provider=None,
                storage_bucket=None,
                storage_key=None,
                storage_size_bytes=None,
                storage_etag=None,
                workspace_id=uuid4(),
                filename="contract.pdf",
                checksum_sha256="checksum",
            )
            fake_session = _FakeSession([doc])
            fake_backend = S3Storage()

            backfill_storage_metadata.SessionLocal = lambda: fake_session
            backfill_storage_metadata.get_storage_backend = lambda: fake_backend
            try:
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )
            finally:
                backfill_storage_metadata.SessionLocal = original_session_local
                backfill_storage_metadata.get_storage_backend = original_get_storage_backend

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(fake_backend.uploads, [])
            self.assertTrue(local_path.is_file())
            self.assertEqual(fake_session.commits, 0)
            self.assertEqual(fake_session.rollbacks, 1)
            self.assertEqual(fake_session.expire_all_calls, 1)
            self.assertTrue(fake_session.closed)


if __name__ == "__main__":
    unittest.main()
