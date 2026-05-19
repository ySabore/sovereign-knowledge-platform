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
    def __init__(self, rows: list[SimpleNamespace], *, fail_commit: bool = False) -> None:
        self.rows = rows
        self.fail_commit = fail_commit
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
        if self.fail_commit:
            raise RuntimeError("commit failed")

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
    def _document_for_path(self, local_path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            storage_path=str(local_path),
            storage_provider="local",
            storage_bucket=None,
            storage_key=str(local_path),
            storage_size_bytes=local_path.stat().st_size,
            storage_etag=None,
            workspace_id=uuid4(),
            filename=local_path.name,
            checksum_sha256="abc123",
            created_at=None,
        )

    def _run_with_fakes(self, *, doc: SimpleNamespace, session: _FakeSession, backend: S3Storage, apply_changes: bool):
        original_session_local = backfill_storage_metadata.SessionLocal
        original_get_storage_backend = backfill_storage_metadata.get_storage_backend
        try:
            backfill_storage_metadata.SessionLocal = lambda: session
            backfill_storage_metadata.get_storage_backend = lambda: backend
            return backfill_storage_metadata.backfill(
                apply_changes=apply_changes,
                upload_local_to_s3=True,
            )
        finally:
            backfill_storage_metadata.SessionLocal = original_session_local
            backfill_storage_metadata.get_storage_backend = original_get_storage_backend

    def test_dry_run_upload_local_to_s3_does_not_upload_or_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "case.txt"
            local_path.write_text("important", encoding="utf-8")
            doc = self._document_for_path(local_path)
            session = _FakeSession([doc])
            backend = S3Storage()

            scanned, updated = self._run_with_fakes(
                doc=doc,
                session=session,
                backend=backend,
                apply_changes=False,
            )

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.uploads, [])
            self.assertTrue(local_path.is_file())
            self.assertEqual(doc.storage_path, str(local_path))
            self.assertEqual(session.rollback_count, 1)
            self.assertEqual(session.commit_count, 0)
            self.assertTrue(session.closed)

    def test_apply_deletes_local_file_only_after_successful_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "case.txt"
            local_path.write_text("important", encoding="utf-8")
            doc = self._document_for_path(local_path)
            session = _FakeSession([doc])
            backend = S3Storage()

            scanned, updated = self._run_with_fakes(
                doc=doc,
                session=session,
                backend=backend,
                apply_changes=True,
            )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.uploads, [local_path])
            self.assertFalse(local_path.exists())
            self.assertEqual(doc.storage_provider, "s3")
            self.assertEqual(session.commit_count, 1)

    def test_apply_keeps_local_file_when_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "case.txt"
            local_path.write_text("important", encoding="utf-8")
            doc = self._document_for_path(local_path)
            session = _FakeSession([doc], fail_commit=True)
            backend = S3Storage()

            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                self._run_with_fakes(
                    doc=doc,
                    session=session,
                    backend=backend,
                    apply_changes=True,
                )

            self.assertEqual(backend.uploads, [local_path])
            self.assertTrue(local_path.is_file())
            self.assertEqual(session.commit_count, 1)
            self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
