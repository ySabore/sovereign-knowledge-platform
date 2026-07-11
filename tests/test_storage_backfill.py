from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class FakeDocument:
    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path
        self.storage_provider = None
        self.storage_bucket = None
        self.storage_key = None
        self.storage_etag = None
        self.storage_size_bytes = 4
        self.workspace_id = uuid4()
        self.filename = "source.txt"
        self.checksum_sha256 = "abc123"


class FakeSession:
    def __init__(self, docs: list[FakeDocument], commit_hook=None) -> None:
        self.docs = docs
        self.commit_hook = commit_hook
        self.commit_calls = 0
        self.rollback_calls = 0
        self.expire_all_calls = 0
        self.close_calls = 0

    def scalars(self, _query):
        return self

    def all(self) -> list[FakeDocument]:
        return self.docs

    def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_hook is not None:
            self.commit_hook()

    def rollback(self) -> None:
        self.rollback_calls += 1

    def expire_all(self) -> None:
        self.expire_all_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class S3Storage:
    def __init__(self) -> None:
        self.store_calls = 0
        self.deleted_uris: list[str] = []

    def store_upload(self, **_kwargs) -> StorageWriteResult:
        self.store_calls += 1
        return StorageWriteResult(
            storage_uri="s3://bucket/key",
            extraction_path=str(_kwargs["local_path"]),
            checksum_sha256="abc123",
            size_bytes=4,
            provider="s3",
            bucket="bucket",
            key="key",
            etag="etag",
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        self.deleted_uris.append(storage_uri)


class StorageMetadataBackfillTests(unittest.TestCase):
    def test_upload_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "source.txt"
            local_path.write_text("data", encoding="utf-8")
            doc = FakeDocument(str(local_path))
            session = FakeSession([doc])
            backend = S3Storage()

            with (
                mock.patch.object(backfill_storage_metadata, "SessionLocal", return_value=session),
                mock.patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=False,
                    upload_local_to_s3=True,
                )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.store_calls, 0)
            self.assertTrue(local_path.is_file())
            self.assertEqual(session.rollback_calls, 1)
            self.assertEqual(session.expire_all_calls, 1)
            self.assertEqual(session.commit_calls, 0)

    def test_upload_apply_deletes_local_file_after_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "source.txt"
            local_path.write_text("data", encoding="utf-8")
            doc = FakeDocument(str(local_path))
            commit_saw_local_file = False

            def commit_hook() -> None:
                nonlocal commit_saw_local_file
                commit_saw_local_file = local_path.is_file()

            session = FakeSession([doc], commit_hook=commit_hook)
            backend = S3Storage()

            with (
                mock.patch.object(backfill_storage_metadata, "SessionLocal", return_value=session),
                mock.patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = backfill_storage_metadata.backfill(
                    apply_changes=True,
                    upload_local_to_s3=True,
                )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.store_calls, 1)
            self.assertTrue(commit_saw_local_file)
            self.assertFalse(local_path.exists())
            self.assertEqual(doc.storage_path, "s3://bucket/key")
            self.assertEqual(session.commit_calls, 1)

    def test_upload_apply_commit_failure_keeps_local_file_and_removes_uploaded_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "source.txt"
            local_path.write_text("data", encoding="utf-8")
            doc = FakeDocument(str(local_path))

            def commit_hook() -> None:
                self.assertTrue(local_path.is_file())
                raise RuntimeError("commit failed")

            session = FakeSession([doc], commit_hook=commit_hook)
            backend = S3Storage()

            with (
                mock.patch.object(backfill_storage_metadata, "SessionLocal", return_value=session),
                mock.patch.object(backfill_storage_metadata, "get_storage_backend", return_value=backend),
            ):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    backfill_storage_metadata.backfill(
                        apply_changes=True,
                        upload_local_to_s3=True,
                    )

            self.assertTrue(local_path.is_file())
            self.assertEqual(backend.deleted_uris, ["s3://bucket/key"])
            self.assertEqual(session.rollback_calls, 1)
            self.assertEqual(session.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
