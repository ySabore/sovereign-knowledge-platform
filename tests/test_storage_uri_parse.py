from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.storage import delete_storage_uri, parse_storage_uri
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

    def test_delete_storage_uri_deletes_plain_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "artifact.txt"
            p.write_text("secret", encoding="utf-8")

            delete_storage_uri(str(p))

            self.assertFalse(p.exists())


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_upload_local_to_s3_dry_run_has_no_artifact_side_effects(self) -> None:
        class _Rows:
            def __init__(self, rows: list[SimpleNamespace]) -> None:
                self._rows = rows

            def all(self) -> list[SimpleNamespace]:
                return self._rows

        class _Db:
            def __init__(self, rows: list[SimpleNamespace]) -> None:
                self._rows = rows
                self.rollback_count = 0
                self.expire_count = 0
                self.commit_count = 0
                self.close_count = 0

            def scalars(self, _stmt: object) -> _Rows:
                return _Rows(self._rows)

            def rollback(self) -> None:
                self.rollback_count += 1

            def expire_all(self) -> None:
                self.expire_count += 1

            def commit(self) -> None:
                self.commit_count += 1

            def close(self) -> None:
                self.close_count += 1

        class S3Storage:
            def __init__(self) -> None:
                self.upload_count = 0

            def store_upload(self, **_kwargs: object) -> object:
                self.upload_count += 1
                raise AssertionError("dry-run must not upload artifacts")

        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "local.pdf"
            local_path.write_bytes(b"pdf bytes")
            doc = SimpleNamespace(
                storage_path=str(local_path),
                storage_provider=None,
                storage_bucket=None,
                storage_key=None,
                storage_size_bytes=None,
                storage_etag=None,
                workspace_id=uuid4(),
                filename="local.pdf",
                checksum_sha256="abc123",
                created_at=None,
            )
            db = _Db([doc])
            backend = S3Storage()

            with (
                patch.object(backfill_storage_metadata, "SessionLocal", return_value=db),
                patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.upload_count, 0)
            self.assertTrue(local_path.is_file())
            self.assertEqual(db.commit_count, 0)
            self.assertEqual(db.rollback_count, 1)
            self.assertEqual(db.expire_count, 1)
            self.assertEqual(db.close_count, 1)


if __name__ == "__main__":
    unittest.main()

