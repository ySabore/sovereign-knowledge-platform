from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class S3Storage:
    def __init__(self) -> None:
        self.uploaded_paths: list[Path] = []
        self.deleted_uris: list[str] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.uploaded_paths.append(local_path)
        return StorageWriteResult(
            storage_uri=f"s3://bucket/{workspace_id}/{safe_name}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key=f"{workspace_id}/{safe_name}",
            etag="etag",
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        self.deleted_uris.append(storage_uri)


class _FakeScalarResult:
    def __init__(self, docs: list[SimpleNamespace]) -> None:
        self.docs = docs

    def all(self) -> list[SimpleNamespace]:
        return self.docs


class _FakeSession:
    def __init__(self, docs: list[SimpleNamespace], commit_error: Exception | None = None) -> None:
        self.docs = docs
        self.commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0
        self.expirations = 0
        self.closed = False

    def scalars(self, _statement) -> _FakeScalarResult:
        return _FakeScalarResult(self.docs)

    def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        self.expirations += 1

    def close(self) -> None:
        self.closed = True


def _document(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider="local",
        storage_bucket=None,
        storage_key=str(path),
        storage_size_bytes=None,
        storage_etag=None,
        workspace_id=uuid4(),
        filename="source.pdf",
        checksum_sha256="abc123",
    )


class StorageBackfillTests(unittest.TestCase):
    def _run_backfill(
        self,
        *,
        doc: SimpleNamespace,
        backend: S3Storage,
        session: _FakeSession,
        apply_changes: bool,
    ) -> tuple[int, int]:
        original_session_local = backfill_storage_metadata.SessionLocal
        original_get_storage_backend = backfill_storage_metadata.get_storage_backend
        try:
            backfill_storage_metadata.SessionLocal = lambda: session
            backfill_storage_metadata.get_storage_backend = lambda: backend
            return backfill_storage_metadata.backfill(apply_changes=apply_changes, upload_local_to_s3=True)
        finally:
            backfill_storage_metadata.SessionLocal = original_session_local
            backfill_storage_metadata.get_storage_backend = original_get_storage_backend

    def test_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "source.pdf"
            local_path.write_text("artifact", encoding="utf-8")
            backend = S3Storage()
            doc = _document(local_path)
            session = _FakeSession([doc])

            self.assertEqual(
                self._run_backfill(doc=doc, backend=backend, session=session, apply_changes=False),
                (1, 1),
            )

            self.assertTrue(local_path.is_file())
            self.assertEqual(backend.uploaded_paths, [])
            self.assertEqual(backend.deleted_uris, [])
            self.assertEqual(session.commits, 0)
            self.assertEqual(session.rollbacks, 1)
            self.assertTrue(session.closed)

    def test_apply_deletes_local_file_only_after_successful_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "source.pdf"
            local_path.write_text("artifact", encoding="utf-8")
            backend = S3Storage()
            doc = _document(local_path)
            session = _FakeSession([doc])

            self.assertEqual(
                self._run_backfill(doc=doc, backend=backend, session=session, apply_changes=True),
                (1, 1),
            )

            self.assertFalse(local_path.exists())
            self.assertEqual(backend.uploaded_paths, [local_path])
            self.assertEqual(backend.deleted_uris, [])
            self.assertEqual(session.commits, 1)
            self.assertEqual(doc.storage_path, f"s3://bucket/{doc.workspace_id}/source.pdf")
            self.assertTrue(session.closed)

    def test_apply_keeps_local_file_and_removes_uploaded_object_when_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "source.pdf"
            local_path.write_text("artifact", encoding="utf-8")
            backend = S3Storage()
            doc = _document(local_path)
            session = _FakeSession([doc], commit_error=RuntimeError("database unavailable"))

            with self.assertRaises(RuntimeError):
                self._run_backfill(doc=doc, backend=backend, session=session, apply_changes=True)

            self.assertTrue(local_path.is_file())
            self.assertEqual(backend.uploaded_paths, [local_path])
            self.assertEqual(backend.deleted_uris, [f"s3://bucket/{doc.workspace_id}/source.pdf"])
            self.assertEqual(session.commits, 1)
            self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
