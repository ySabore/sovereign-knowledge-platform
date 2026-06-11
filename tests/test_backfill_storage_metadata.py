from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.services.storage import StorageWriteResult
from scripts import backfill_storage_metadata


class FakeScalarResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.commits = 0
        self.rollbacks = 0
        self.expired = 0
        self.closed = False
        self.on_commit = None

    def scalars(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult(self.rows)

    def commit(self) -> None:
        if self.on_commit is not None:
            self.on_commit()
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def expire_all(self) -> None:
        self.expired += 1

    def close(self) -> None:
        self.closed = True


class S3Storage:
    def __init__(self, storage_uri: str = "s3://bucket/key") -> None:
        self.storage_uri = storage_uri
        self.uploads = 0
        self.deleted: list[str] = []

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: object,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        self.uploads += 1
        return StorageWriteResult(
            storage_uri=self.storage_uri,
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket="bucket",
            key="key",
            etag="etag",
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        self.deleted.append(storage_uri)


def _document(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        storage_path=str(path),
        storage_provider=None,
        storage_bucket=None,
        storage_key=None,
        storage_size_bytes=None,
        storage_etag=None,
        workspace_id=uuid4(),
        filename="document.txt",
        checksum_sha256="abc123",
    )


def test_upload_local_to_s3_dry_run_does_not_upload_or_delete(monkeypatch, tmp_path) -> None:
    local_path = tmp_path / "document.txt"
    local_path.write_text("content", encoding="utf-8")
    doc = _document(local_path)
    session = FakeSession([doc])
    backend = S3Storage()

    def fail_upload(**kwargs) -> StorageWriteResult:
        raise AssertionError("dry-run must not upload")

    backend.store_upload = fail_upload
    monkeypatch.setattr(backfill_storage_metadata, "SessionLocal", lambda: session)
    monkeypatch.setattr(backfill_storage_metadata, "get_storage_backend", lambda: backend)

    scanned, updated = backfill_storage_metadata.backfill(apply_changes=False, upload_local_to_s3=True)

    assert (scanned, updated) == (1, 1)
    assert local_path.exists()
    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.expired == 1


def test_upload_local_to_s3_deletes_local_only_after_commit(monkeypatch, tmp_path) -> None:
    local_path = tmp_path / "document.txt"
    local_path.write_text("content", encoding="utf-8")
    doc = _document(local_path)
    session = FakeSession([doc])
    backend = S3Storage(storage_uri="s3://bucket/workspace/document.txt")

    def assert_file_exists_during_commit() -> None:
        assert local_path.exists()

    session.on_commit = assert_file_exists_during_commit
    monkeypatch.setattr(backfill_storage_metadata, "SessionLocal", lambda: session)
    monkeypatch.setattr(backfill_storage_metadata, "get_storage_backend", lambda: backend)

    scanned, updated = backfill_storage_metadata.backfill(apply_changes=True, upload_local_to_s3=True)

    assert (scanned, updated) == (1, 1)
    assert session.commits == 1
    assert not local_path.exists()
    assert backend.uploads == 1
    assert doc.storage_path == "s3://bucket/workspace/document.txt"
    assert doc.storage_provider == "s3"

