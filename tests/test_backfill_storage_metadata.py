from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import tempfile
import unittest

from scripts import backfill_storage_metadata


class _ScalarRows:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace], *, fail_commit: bool = False) -> None:
        self._rows = rows
        self._fail_commit = fail_commit
        self.commit_calls = 0
        self.rollback_calls = 0
        self.expire_all_calls = 0
        self.closed = False

    def scalars(self, _statement: object) -> _ScalarRows:
        return _ScalarRows(self._rows)

    def commit(self) -> None:
        self.commit_calls += 1
        if self._fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollback_calls += 1

    def expire_all(self) -> None:
        self.expire_all_calls += 1

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self) -> None:
        self.uploads: list[Path] = []

    def store_upload(self, *, local_path: Path, workspace_id, safe_name: str, checksum_sha256: str, size_bytes: int):
        self.uploads.append(local_path)
        return SimpleNamespace(
            storage_uri=f"s3://bucket/{workspace_id}/{safe_name}",
            provider="s3",
            bucket="bucket",
            key=f"{workspace_id}/{safe_name}",
            etag="etag",
            size_bytes=size_bytes,
        )


def _document_for(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider="local",
        storage_bucket=None,
        storage_key=str(path),
        storage_size_bytes=None,
        storage_etag=None,
        workspace_id=uuid4(),
        filename=path.name,
        checksum_sha256="abc123",
    )


class BackfillStorageMetadataTests(unittest.TestCase):
    def _run_backfill(
        self,
        *,
        apply_changes: bool,
        fail_commit: bool = False,
        path: Path,
    ) -> tuple[_FakeSession, S3Storage, tuple[int, int]]:
        doc = _document_for(path)
        session = _FakeSession([doc], fail_commit=fail_commit)
        backend = S3Storage()
        with patch.object(backfill_storage_metadata, "SessionLocal", return_value=session), patch.object(
            backfill_storage_metadata, "get_storage_backend", return_value=backend
        ):
            result = backfill_storage_metadata.backfill(
                apply_changes=apply_changes,
                upload_local_to_s3=True,
            )
        return session, backend, result

    def test_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "doc.txt"
            path.write_text("contents", encoding="utf-8")

            session, backend, result = self._run_backfill(apply_changes=False, path=path)

            self.assertEqual(result, (1, 1))
            self.assertEqual(len(backend.uploads), 0)
            self.assertTrue(path.exists())
            self.assertEqual(session.rollback_calls, 1)

    def test_apply_keeps_local_file_when_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "doc.txt"
            path.write_text("contents", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                self._run_backfill(apply_changes=True, fail_commit=True, path=path)

            self.assertTrue(path.exists())

    def test_apply_deletes_local_file_only_after_successful_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "doc.txt"
            path.write_text("contents", encoding="utf-8")

            session, backend, result = self._run_backfill(apply_changes=True, path=path)

            self.assertEqual(result, (1, 1))
            self.assertEqual(session.commit_calls, 1)
            self.assertEqual(len(backend.uploads), 1)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
