"""Regression: durable deletes must commit before storage artifact unlinks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Document, DocumentStatus, Organization, OrgStatus, Workspace
from app.services import resource_cleanup


class DeleteArtifactOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.tmp = tempfile.TemporaryDirectory()
        self.artifact = Path(self.tmp.name) / "doc.pdf"
        self.artifact.write_bytes(b"%PDF-1.4 test")

        db = self.SessionLocal()
        try:
            org = Organization(
                name="Cleanup Org",
                slug=f"cleanup-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
                plan="free",
            )
            db.add(org)
            db.flush()
            ws = Workspace(organization_id=org.id, name="Main")
            db.add(ws)
            db.flush()
            doc = Document(
                organization_id=org.id,
                workspace_id=ws.id,
                filename="doc.pdf",
                content_type="application/pdf",
                storage_path=str(self.artifact.resolve()),
                source_type="upload",
                status=DocumentStatus.indexed.value,
            )
            db.add(doc)
            db.commit()
            self.org_id = org.id
            self.workspace_id = ws.id
            self.document_id = doc.id
        finally:
            db.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self.engine.dispose()

    def test_cascade_returns_paths_without_unlinking(self) -> None:
        db = self.SessionLocal()
        try:
            paths = resource_cleanup.delete_workspace_cascade(db, self.workspace_id)
            self.assertEqual(paths, [str(self.artifact.resolve())])
            self.assertTrue(self.artifact.is_file(), "artifact must remain until post-commit unlink")
            db.rollback()
        finally:
            db.close()
        self.assertTrue(self.artifact.is_file())

    def test_failed_commit_preserves_artifact_for_document_delete(self) -> None:
        db = self.SessionLocal()
        deleted_uris: list[str] = []

        def _track_delete(uri: str) -> None:
            deleted_uris.append(uri)
            Path(uri).unlink(missing_ok=True)

        try:
            path = resource_cleanup.collect_document_storage_path(db, self.document_id)
            self.assertEqual(path, str(self.artifact.resolve()))
            from sqlalchemy import delete

            db.execute(delete(Document).where(Document.id == self.document_id))
            with (
                patch.object(db, "commit", side_effect=RuntimeError("simulated commit failure")),
                patch.object(resource_cleanup, "_unlink_storage_path", side_effect=_track_delete),
            ):
                with self.assertRaises(RuntimeError):
                    db.commit()
                    resource_cleanup.unlink_storage_paths([path])
            self.assertEqual(deleted_uris, [])
            self.assertTrue(self.artifact.is_file())
            db.rollback()
        finally:
            db.close()

        # Row must still exist after rollback; artifact still on disk.
        db = self.SessionLocal()
        try:
            doc = db.get(Document, self.document_id)
            self.assertIsNotNone(doc)
            self.assertEqual(doc.storage_path, str(self.artifact.resolve()))
            self.assertTrue(Path(doc.storage_path).is_file())
        finally:
            db.close()

    def test_successful_commit_then_unlink_removes_artifact(self) -> None:
        db = self.SessionLocal()
        try:
            path = resource_cleanup.collect_document_storage_path(db, self.document_id)
            from sqlalchemy import delete

            db.execute(delete(Document).where(Document.id == self.document_id))
            db.commit()
            resource_cleanup.unlink_storage_paths([path])
        finally:
            db.close()

        self.assertFalse(self.artifact.exists())
        db = self.SessionLocal()
        try:
            self.assertIsNone(db.get(Document, self.document_id))
        finally:
            db.close()

    def test_organization_cascade_defers_unlink_until_after_commit(self) -> None:
        db = self.SessionLocal()
        try:
            paths = resource_cleanup.delete_organization_cascade(db, self.org_id)
            self.assertEqual(paths, [str(self.artifact.resolve())])
            self.assertTrue(self.artifact.is_file())
            db.commit()
            resource_cleanup.unlink_storage_paths(paths)
        finally:
            db.close()
        self.assertFalse(self.artifact.exists())


if __name__ == "__main__":
    unittest.main()
