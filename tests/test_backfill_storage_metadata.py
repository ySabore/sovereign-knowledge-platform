"""Local document bytes must survive a dry-run and a failed commit of the S3 backfill."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.storage import StorageWriteResult


def _load_backfill():
    path = Path(__file__).resolve().parents[1] / "scripts" / "backfill_storage_metadata.py"
    spec = importlib.util.spec_from_file_location("backfill_storage_metadata", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class S3Storage:
    def __init__(self) -> None:
        self.uploads: list[Path] = []

    def store_upload(self, *, local_path: Path, workspace_id, safe_name: str, checksum_sha256: str, size_bytes: int):
        self.uploads.append(local_path)
        _ = (workspace_id, safe_name, checksum_sha256, size_bytes)
        return StorageWriteResult(
            storage_uri="s3://bucket/key",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256 or "abc",
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key="key",
            etag="etag",
        )


class _Session:
    def __init__(self, rows: list[object], *, commit_error: Exception | None = None) -> None:
        self._rows = rows
        self.commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def scalars(self, _stmt):
        rows = self._rows
        return SimpleNamespace(all=lambda: rows)

    def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class BackfillStorageMetadataTests(unittest.TestCase):
    def test_dry_run_does_not_upload_or_delete_local_file(self) -> None:
        module = _load_backfill()
        backend = S3Storage()
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "policy.pdf"
            local.write_bytes(b"policy")
            doc = SimpleNamespace(
                storage_path=str(local),
                storage_provider=None,
                storage_bucket=None,
                storage_key=None,
                storage_size_bytes=None,
                storage_etag=None,
                filename="policy.pdf",
                checksum_sha256="abc",
                workspace_id=uuid.uuid4(),
            )
            session = _Session([doc])
            with (
                patch.object(module, "SessionLocal", return_value=session),
                patch.object(module, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = module.backfill(apply_changes=False, upload_local_to_s3=True)

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(backend.uploads, [])
            self.assertTrue(local.is_file())
            self.assertEqual(doc.storage_path, str(local))
            self.assertEqual(session.commits, 0)
            self.assertGreaterEqual(session.rollbacks, 1)
            self.assertTrue(session.closed)

    def test_apply_deletes_local_file_only_after_commit(self) -> None:
        module = _load_backfill()
        backend = S3Storage()
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "policy.pdf"
            local.write_bytes(b"policy")
            doc = SimpleNamespace(
                storage_path=str(local),
                storage_provider="local",
                storage_bucket=None,
                storage_key=str(local),
                storage_size_bytes=local.stat().st_size,
                storage_etag=None,
                filename="policy.pdf",
                checksum_sha256="abc",
                workspace_id=uuid.uuid4(),
            )
            existed_at_commit: list[bool] = []

            class _CommitSession(_Session):
                def commit(self) -> None:
                    existed_at_commit.append(local.is_file())
                    super().commit()

            session = _CommitSession([doc])
            with (
                patch.object(module, "SessionLocal", return_value=session),
                patch.object(module, "get_storage_backend", return_value=backend),
            ):
                scanned, updated = module.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual((scanned, updated), (1, 1))
            self.assertEqual(len(backend.uploads), 1)
            self.assertEqual(existed_at_commit, [True])
            self.assertFalse(local.exists())
            self.assertEqual(doc.storage_path, "s3://bucket/key")
            self.assertEqual(session.commits, 1)

    def test_apply_keeps_local_file_when_commit_fails(self) -> None:
        module = _load_backfill()
        backend = S3Storage()
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "policy.pdf"
            local.write_bytes(b"policy")
            original = str(local)
            doc = SimpleNamespace(
                storage_path=original,
                storage_provider="local",
                storage_bucket=None,
                storage_key=original,
                storage_size_bytes=local.stat().st_size,
                storage_etag=None,
                filename="policy.pdf",
                checksum_sha256="abc",
                workspace_id=uuid.uuid4(),
            )
            session = _Session([doc], commit_error=RuntimeError("database unavailable"))
            with (
                patch.object(module, "SessionLocal", return_value=session),
                patch.object(module, "get_storage_backend", return_value=backend),
            ):
                with self.assertRaises(RuntimeError):
                    module.backfill(apply_changes=True, upload_local_to_s3=True)

            self.assertEqual(len(backend.uploads), 1)
            self.assertTrue(local.is_file())
            self.assertEqual(local.read_bytes(), b"policy")
            self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
