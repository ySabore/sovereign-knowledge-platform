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


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace], *, fail_commit: bool = False) -> None:
        self._rows = rows
        self.fail_commit = fail_commit
        self.commit_called = False
        self.rollback_count = 0
        self.expire_all_count = 0
        self.closed = False

    def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self._rows)

    def commit(self) -> None:
        self.commit_called = True
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollback_count += 1

    def expire_all(self) -> None:
        self.expire_all_count += 1

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.deleted: list[str] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: object,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> SimpleNamespace:
        key = f"{workspace_id}/{safe_name}"
        uri = f"s3://bucket/{key}"
        self.uploaded.append(uri)
        return SimpleNamespace(
            storage_uri=uri,
            provider="s3",
            bucket="bucket",
            key=key,
            etag="etag-1",
            size_bytes=size_bytes,
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        self.deleted.append(storage_uri)


def _document_for_path(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider=None,
        storage_bucket=None,
        storage_key=None,
        storage_size_bytes=None,
        storage_etag=None,
        checksum_sha256="abc123",
        workspace_id=uuid4(),
        filename=path.name,
        created_at=None,
    )


class StorageBackfillTests(unittest.TestCase):
    def _run_with_fakes(
        self,
        *,
        db: _FakeSession,
        backend: S3Storage,
        apply_changes: bool,
        upload_local_to_s3: bool,
    ) -> tuple[int, int]:
        original_session_local = backfill_storage_metadata.SessionLocal
        original_backend_factory = backfill_storage_metadata.get_storage_backend
        backfill_storage_metadata.SessionLocal = lambda: db  # type: ignore[assignment]
        backfill_storage_metadata.get_storage_backend = lambda: backend  # type: ignore[assignment]
        try:
            return backfill_storage_metadata.backfill(
                apply_changes=apply_changes,
                upload_local_to_s3=upload_local_to_s3,
            )
        finally:
            backfill_storage_metadata.SessionLocal = original_session_local
            backfill_storage_metadata.get_storage_backend = original_backend_factory

    def test_dry_run_does_not_upload_or_delete_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "doc.txt"
            local_path.write_text("important content", encoding="utf-8")
            doc = _document_for_path(local_path)
            db = _FakeSession([doc])
            backend = S3Storage()

            scanned, updated = self._run_with_fakes(
                db=db,
                backend=backend,
                apply_changes=False,
                upload_local_to_s3=True,
            )

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.uploaded, [])
            self.assertEqual(backend.deleted, [])
            self.assertTrue(local_path.exists())
            self.assertFalse(db.commit_called)
            self.assertEqual(db.rollback_count, 1)
            self.assertTrue(db.closed)

    def test_commit_failure_preserves_local_artifact_and_cleans_uploaded_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "doc.txt"
            local_path.write_text("important content", encoding="utf-8")
            doc = _document_for_path(local_path)
            db = _FakeSession([doc], fail_commit=True)
            backend = S3Storage()

            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                self._run_with_fakes(
                    db=db,
                    backend=backend,
                    apply_changes=True,
                    upload_local_to_s3=True,
                )

            self.assertTrue(local_path.exists())
            self.assertEqual(len(backend.uploaded), 1)
            self.assertEqual(backend.deleted, backend.uploaded)
            self.assertEqual(db.rollback_count, 1)
            self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
