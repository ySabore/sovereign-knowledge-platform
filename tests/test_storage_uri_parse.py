from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.config import settings
from app.services.storage import S3Storage, delete_storage_uri, parse_storage_uri
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

    def test_delete_storage_uri_removes_local_path_independent_of_backend(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.txt"
            path.write_text("confidential", encoding="utf-8")

            delete_storage_uri(str(path))

            self.assertFalse(path.exists())

    def test_s3_upload_tolerates_missing_head_object_permission(self) -> None:
        old_bucket = settings.s3_bucket
        old_prefix = settings.s3_prefix
        try:
            settings.s3_bucket = "documents"
            settings.s3_prefix = ""
            client = Mock()
            client.head_object.side_effect = RuntimeError("AccessDenied")
            with TemporaryDirectory() as tmp, patch("boto3.client", return_value=client):
                path = Path(tmp) / "document.txt"
                path.write_text("content", encoding="utf-8")
                stored = S3Storage().store_upload(
                    local_path=path,
                    workspace_id=uuid4(),
                    safe_name="document.txt",
                    checksum_sha256="abc123",
                    size_bytes=7,
                )

            self.assertEqual(stored.provider, "s3")
            self.assertEqual(stored.bucket, "documents")
            self.assertIsNone(stored.etag)
            client.upload_file.assert_called_once()
        finally:
            settings.s3_bucket = old_bucket
            settings.s3_prefix = old_prefix

    def test_backfill_dry_run_upload_to_s3_has_no_file_side_effects(self) -> None:
        class S3Storage:
            upload_called = False

            def store_upload(self, **_: object) -> object:
                self.upload_called = True
                raise AssertionError("dry-run must not upload")

        class FakeDb:
            def __init__(self, docs: list[object]) -> None:
                self.docs = docs
                self.commits = 0
                self.rollbacks = 0

            def scalars(self, _: object) -> object:
                return SimpleNamespace(all=lambda: self.docs)

            def commit(self) -> None:
                self.commits += 1

            def rollback(self) -> None:
                self.rollbacks += 1

            def expire_all(self) -> None:
                pass

            def close(self) -> None:
                pass

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.txt"
            path.write_text("legacy", encoding="utf-8")
            doc = SimpleNamespace(
                storage_path=str(path),
                storage_provider=None,
                storage_bucket=None,
                storage_key=None,
                storage_size_bytes=None,
                storage_etag=None,
                workspace_id=uuid4(),
                filename="legacy.txt",
                checksum_sha256="abc123",
            )
            fake_db = FakeDb([doc])
            backend = S3Storage()
            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=fake_db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual((scanned, updated), (1, 1))
            self.assertFalse(backend.upload_called)
            self.assertTrue(path.exists())
            self.assertEqual(fake_db.commits, 0)
            self.assertEqual(fake_db.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()

