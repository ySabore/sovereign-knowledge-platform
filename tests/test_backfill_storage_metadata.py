from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from scripts import backfill_storage_metadata


class _ScalarResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows
        self.rollbacks = 0
        self.commits = 0

    def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self._rows)

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        return None


class S3Storage:
    def __init__(self) -> None:
        self.uploads = 0

    def store_upload(self, **_kwargs: object) -> object:
        self.uploads += 1
        raise AssertionError("dry-run backfill must not upload local files")


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_upload_local_to_s3_has_no_external_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_file = Path(tmpdir) / "artifact.pdf"
            local_file.write_bytes(b"pdf bytes")
            doc = SimpleNamespace(
                created_at=1,
                filename="artifact.pdf",
                workspace_id=uuid4(),
                checksum_sha256="abc123",
                storage_path=str(local_file),
                storage_provider="local",
                storage_bucket=None,
                storage_key=str(local_file),
                storage_etag=None,
                storage_size_bytes=local_file.stat().st_size,
            )
            fake_db = _FakeDb([doc])
            fake_storage = S3Storage()
            original_session = backfill_storage_metadata.SessionLocal
            original_backend = backfill_storage_metadata.get_storage_backend
            backfill_storage_metadata.SessionLocal = lambda: fake_db  # type: ignore[assignment]
            backfill_storage_metadata.get_storage_backend = lambda: fake_storage  # type: ignore[assignment]
            try:
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )
            finally:
                backfill_storage_metadata.SessionLocal = original_session  # type: ignore[assignment]
                backfill_storage_metadata.get_storage_backend = original_backend  # type: ignore[assignment]

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(fake_storage.uploads, 0)
            self.assertEqual(fake_db.rollbacks, 1)
            self.assertEqual(fake_db.commits, 0)
            self.assertTrue(local_file.is_file())
            self.assertEqual(doc.storage_path, str(local_file))


if __name__ == "__main__":
    unittest.main()
