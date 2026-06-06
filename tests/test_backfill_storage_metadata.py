from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, Organization, OrgStatus, Workspace
from scripts.backfill_storage_metadata import backfill


class S3Storage:
    def __init__(self) -> None:
        self.upload_calls = 0

    def store_upload(self, **_kwargs):
        self.upload_calls += 1
        raise AssertionError("dry-run must not upload or delete artifacts")


class StorageMetadataBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_dry_run_upload_local_to_s3_has_no_storage_side_effects(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "document.txt"
            artifact.write_text("sensitive document", encoding="utf-8")
            db = self.SessionLocal()
            try:
                org = Organization(
                    name="Backfill Org",
                    slug=f"backfill-{uuid4().hex[:8]}",
                    tenant_key=f"tenant-{uuid4().hex[:8]}",
                    status=OrgStatus.active.value,
                )
                db.add(org)
                db.flush()
                workspace = Workspace(organization_id=org.id, name="Backfill Workspace")
                db.add(workspace)
                db.flush()
                db.add(
                    Document(
                        organization_id=org.id,
                        workspace_id=workspace.id,
                        filename="document.txt",
                        content_type="text/plain",
                        storage_path=str(artifact),
                        source_type="file-upload",
                        external_id=str(uuid4()),
                        status="indexed",
                    )
                )
                db.commit()
            finally:
                db.close()

            backend = S3Storage()
            scanned, updated = backfill(
                apply_changes=False,
                upload_local_to_s3=True,
                session_factory=self.SessionLocal,
                backend=backend,
            )

            self.assertEqual(scanned, 1)
            self.assertEqual(updated, 1)
            self.assertEqual(backend.upload_calls, 0)
            self.assertTrue(artifact.exists())


if __name__ == "__main__":
    unittest.main()
