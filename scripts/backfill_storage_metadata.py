from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Document
from app.services.storage import get_storage_backend, parse_storage_uri


def backfill(*, apply_changes: bool, upload_local_to_s3: bool) -> tuple[int, int]:
    scanned = 0
    updated = 0
    backend = get_storage_backend()
    db = SessionLocal()
    try:
        rows = db.scalars(select(Document).order_by(Document.created_at.asc())).all()
        for doc in rows:
            scanned += 1
            parsed = parse_storage_uri(doc.storage_path)
            changed = False

            if doc.storage_provider != parsed.provider:
                doc.storage_provider = parsed.provider
                changed = True
            if doc.storage_bucket != parsed.bucket:
                doc.storage_bucket = parsed.bucket
                changed = True
            if doc.storage_key != parsed.key:
                doc.storage_key = parsed.key
                changed = True
            if doc.storage_size_bytes is None:
                local_path = (doc.storage_path or "").strip()
                if local_path and "://" not in local_path and Path(local_path).is_file():
                    doc.storage_size_bytes = int(Path(local_path).stat().st_size)
                    changed = True

            should_migrate = (
                upload_local_to_s3
                and parsed.provider == "local"
                and getattr(backend, "__class__", type(backend)).__name__ == "S3Storage"
            )
            if should_migrate:
                local_path = Path(doc.storage_path)
                if local_path.is_file():
                    stored = backend.store_upload(
                        local_path=local_path,
                        workspace_id=doc.workspace_id,
                        safe_name=Path(doc.filename or "document").name,
                        checksum_sha256=doc.checksum_sha256 or "",
                        size_bytes=int(doc.storage_size_bytes or local_path.stat().st_size),
                    )
                    doc.storage_path = stored.storage_uri
                    doc.storage_provider = stored.provider
                    doc.storage_bucket = stored.bucket
                    doc.storage_key = stored.key
                    doc.storage_etag = stored.etag
                    doc.storage_size_bytes = stored.size_bytes
                    local_path.unlink(missing_ok=True)
                    changed = True

            if changed:
                updated += 1
                if not apply_changes:
                    db.rollback()
                    db.expire_all()
        if apply_changes:
            db.commit()
    finally:
        db.close()
    return scanned, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill document storage metadata and optional local->S3 migration.")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    parser.add_argument(
        "--upload-local-to-s3",
        action="store_true",
        help="When STORAGE_BACKEND=s3, upload local filesystem artifacts to S3 and rewrite storage_path.",
    )
    args = parser.parse_args()
    scanned, updated = backfill(apply_changes=bool(args.apply), upload_local_to_s3=bool(args.upload_local_to_s3))
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] scanned={scanned} updated={updated}")


if __name__ == "__main__":
    main()

