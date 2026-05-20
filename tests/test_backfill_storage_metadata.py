from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts.backfill_storage_metadata import _migrate_local_artifact_to_s3


class _FakeS3Backend:
    def __init__(self) -> None:
        self.upload_count = 0

    def store_upload(self, **kwargs) -> StorageWriteResult:
        self.upload_count += 1
        local_path = Path(kwargs["local_path"])
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{local_path.name}",
            extraction_path=str(local_path),
            checksum_sha256=kwargs["checksum_sha256"],
            size_bytes=kwargs["size_bytes"],
            provider="s3",
            bucket="bucket",
            key=local_path.name,
            etag="etag",
        )


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_does_not_upload_or_delete_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.txt"
            path.write_text("hello", encoding="utf-8")
            doc = SimpleNamespace(
                storage_path=str(path),
                workspace_id=uuid4(),
                filename="document.txt",
                checksum_sha256="abc123",
                storage_size_bytes=path.stat().st_size,
            )
            backend = _FakeS3Backend()

            migrated, local_path_to_delete = _migrate_local_artifact_to_s3(doc, backend, apply_changes=False)

            self.assertTrue(migrated)
            self.assertIsNone(local_path_to_delete)
            self.assertEqual(backend.upload_count, 0)
            self.assertEqual(doc.storage_path, str(path))
            self.assertTrue(path.exists())

    def test_apply_uploads_but_defers_local_delete_to_caller(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.txt"
            path.write_text("hello", encoding="utf-8")
            doc = SimpleNamespace(
                storage_path=str(path),
                workspace_id=uuid4(),
                filename="document.txt",
                checksum_sha256="abc123",
                storage_size_bytes=path.stat().st_size,
            )
            backend = _FakeS3Backend()

            migrated, local_path_to_delete = _migrate_local_artifact_to_s3(doc, backend, apply_changes=True)

            self.assertTrue(migrated)
            self.assertEqual(local_path_to_delete, path)
            self.assertEqual(backend.upload_count, 1)
            self.assertEqual(doc.storage_path, "s3://bucket/document.txt")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
