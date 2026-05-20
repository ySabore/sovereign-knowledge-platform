from __future__ import annotations

import unittest
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models import ConnectorSyncJob, Document, IntegrationConnector, Organization, Workspace, utcnow
from app.routers.connectors import PermissionSyncItem, _validate_permission_sync_scope
from app.services.sync_orchestrator import (
    SYNC_JOB_FAILED,
    SYNC_JOB_QUEUED,
    SYNC_JOB_RUNNING,
    enqueue_connector_sync_job,
)


class ConnectorCorrectnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def _seed_connector(self):
        db = self.SessionLocal()
        org = Organization(name="Org", slug=f"org-{uuid4().hex[:8]}", tenant_key=f"tenant-{uuid4().hex[:8]}")
        db.add(org)
        db.flush()
        workspace = Workspace(organization_id=org.id, name="Workspace")
        db.add(workspace)
        db.flush()
        connector = IntegrationConnector(
            organization_id=org.id,
            connector_type="google-drive",
            nango_connection_id="conn-1",
            status="active",
        )
        db.add(connector)
        db.commit()
        return db, org, workspace, connector

    def test_stale_running_sync_job_does_not_block_requeue(self) -> None:
        db, org, workspace, connector = self._seed_connector()
        try:
            stale_job = ConnectorSyncJob(
                connector_id=connector.id,
                organization_id=org.id,
                workspace_id=workspace.id,
                status=SYNC_JOB_RUNNING,
                started_at=utcnow() - timedelta(seconds=settings.connector_sync_job_stale_after_seconds + 1),
            )
            db.add(stale_job)
            db.commit()
            stale_job_id = stale_job.id

            new_job, created = enqueue_connector_sync_job(
                db,
                connector_id=connector.id,
                organization_id=org.id,
                workspace_id=workspace.id,
                requested_by_user_id=None,
                full_sync=False,
            )

            db.refresh(stale_job)
            self.assertTrue(created)
            self.assertNotEqual(new_job.id, stale_job_id)
            self.assertEqual(stale_job.status, SYNC_JOB_FAILED)
            self.assertEqual(new_job.status, SYNC_JOB_QUEUED)
        finally:
            db.close()

    def test_permission_sync_rejects_cross_org_batch(self) -> None:
        db = self.SessionLocal()
        try:
            org_a = Organization(name="Org A", slug=f"orga-{uuid4().hex[:8]}", tenant_key=f"ta-{uuid4().hex[:8]}")
            org_b = Organization(name="Org B", slug=f"orgb-{uuid4().hex[:8]}", tenant_key=f"tb-{uuid4().hex[:8]}")
            db.add_all([org_a, org_b])
            db.flush()

            with self.assertRaises(HTTPException) as ctx:
                _validate_permission_sync_scope(
                    db,
                    org_a.id,
                    [
                        PermissionSyncItem(
                            document_id=uuid4(),
                            organization_id=org_a.id,
                            source="drive",
                            external_id="a",
                        ),
                        PermissionSyncItem(
                            document_id=uuid4(),
                            organization_id=org_b.id,
                            source="drive",
                            external_id="b",
                        ),
                    ],
                )

            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            db.close()

    def test_permission_sync_rejects_document_outside_authorized_org(self) -> None:
        db = self.SessionLocal()
        try:
            org_a = Organization(name="Org A", slug=f"orga-{uuid4().hex[:8]}", tenant_key=f"ta-{uuid4().hex[:8]}")
            org_b = Organization(name="Org B", slug=f"orgb-{uuid4().hex[:8]}", tenant_key=f"tb-{uuid4().hex[:8]}")
            db.add_all([org_a, org_b])
            db.flush()
            workspace_b = Workspace(organization_id=org_b.id, name="Workspace B")
            db.add(workspace_b)
            db.flush()
            doc_b = Document(
                organization_id=org_b.id,
                workspace_id=workspace_b.id,
                filename="foreign.txt",
                content_type="text/plain",
                storage_path="inline://drive/foreign",
                source_type="drive",
                external_id="foreign",
                status="indexed",
            )
            db.add(doc_b)
            db.commit()

            with self.assertRaises(HTTPException) as ctx:
                _validate_permission_sync_scope(
                    db,
                    org_a.id,
                    [
                        PermissionSyncItem(
                            document_id=doc_b.id,
                            organization_id=org_a.id,
                            source="drive",
                            external_id="foreign",
                        )
                    ],
                )

            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
