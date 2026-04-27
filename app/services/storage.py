from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from app.config import settings


@dataclass(slots=True)
class StorageWriteResult:
    storage_uri: str
    extraction_path: str
    checksum_sha256: str
    size_bytes: int
    provider: str
    bucket: str | None
    key: str | None
    etag: str | None = None


class BaseStorage:
    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: UUID,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        raise NotImplementedError

    def delete_by_uri(self, storage_uri: str) -> None:
        raise NotImplementedError


class LocalFileStorage(BaseStorage):
    def __init__(self, root: Path) -> None:
        self.root = root

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: UUID,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        destination_dir = self.root / str(workspace_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / f"{uuid4()}-{safe_name}"
        shutil.move(str(local_path), str(destination_path))
        resolved = str(destination_path.resolve())
        return StorageWriteResult(
            storage_uri=resolved,
            extraction_path=resolved,
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="local",
            bucket=None,
            key=resolved,
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        if not storage_uri:
            return
        if "://" in storage_uri and not storage_uri.startswith("local://"):
            return
        raw = storage_uri.removeprefix("local://")
        path = Path(raw)
        if path.is_file():
            path.unlink()


class S3Storage(BaseStorage):
    def __init__(self) -> None:
        try:
            import boto3
        except Exception as exc:
            raise RuntimeError("STORAGE_BACKEND=s3 requires boto3 installed") from exc
        kwargs: dict = {}
        if settings.s3_region.strip():
            kwargs["region_name"] = settings.s3_region.strip()
        if settings.s3_endpoint_url.strip():
            kwargs["endpoint_url"] = settings.s3_endpoint_url.strip()
        if settings.s3_access_key_id.strip():
            kwargs["aws_access_key_id"] = settings.s3_access_key_id.strip()
        if settings.s3_secret_access_key.strip():
            kwargs["aws_secret_access_key"] = settings.s3_secret_access_key.strip()
        self.client = boto3.client("s3", **kwargs)
        self.bucket = settings.s3_bucket.strip()
        if not self.bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET")

    def _build_key(self, workspace_id: UUID, safe_name: str) -> str:
        prefix = settings.s3_prefix.strip().strip("/")
        parts = [p for p in [prefix, str(workspace_id), f"{uuid4()}-{safe_name}"] if p]
        return "/".join(parts)

    def store_upload(
        self,
        *,
        local_path: Path,
        workspace_id: UUID,
        safe_name: str,
        checksum_sha256: str,
        size_bytes: int,
    ) -> StorageWriteResult:
        key = self._build_key(workspace_id, safe_name)
        extra: dict[str, str] = {"Metadata": {"sha256": checksum_sha256}}
        if settings.s3_sse_mode.strip():
            extra["ServerSideEncryption"] = settings.s3_sse_mode.strip()
        if settings.s3_kms_key_id.strip():
            extra["SSEKMSKeyId"] = settings.s3_kms_key_id.strip()
        self.client.upload_file(str(local_path), self.bucket, key, ExtraArgs=extra)
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        etag = str(head.get("ETag") or "").strip().strip('"') or None
        return StorageWriteResult(
            storage_uri=f"s3://{self.bucket}/{key}",
            extraction_path=str(local_path),
            checksum_sha256=checksum_sha256,
            size_bytes=size_bytes,
            provider="s3",
            bucket=self.bucket,
            key=key,
            etag=etag,
        )

    def delete_by_uri(self, storage_uri: str) -> None:
        if not storage_uri.startswith("s3://"):
            return
        payload = storage_uri[len("s3://") :]
        bucket, _, key = payload.partition("/")
        if not bucket or not key:
            return
        self.client.delete_object(Bucket=bucket, Key=key)


def get_storage_backend() -> BaseStorage:
    backend = settings.storage_backend.strip().lower()
    if backend == "s3":
        return S3Storage()
    return LocalFileStorage(settings.document_storage_root)


def cleanup_temp_extraction_file(extraction_path: str, storage_uri: str) -> None:
    if not extraction_path:
        return
    if extraction_path == storage_uri:
        return
    p = Path(extraction_path)
    if p.is_file():
        p.unlink(missing_ok=True)


@dataclass(slots=True)
class ParsedStorageUri:
    provider: str | None
    bucket: str | None
    key: str | None


def parse_storage_uri(storage_uri: str | None) -> ParsedStorageUri:
    raw = (storage_uri or "").strip()
    if not raw:
        return ParsedStorageUri(provider=None, bucket=None, key=None)
    if raw.startswith("s3://"):
        payload = raw[len("s3://") :]
        bucket, _, key = payload.partition("/")
        return ParsedStorageUri(provider="s3", bucket=bucket or None, key=key or None)
    if raw.startswith("local://"):
        key = raw.removeprefix("local://")
        return ParsedStorageUri(provider="local", bucket=None, key=key or None)
    return ParsedStorageUri(provider="local", bucket=None, key=raw)

