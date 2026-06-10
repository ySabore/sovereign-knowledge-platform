from __future__ import annotations

from datetime import timedelta
import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models import ConnectorSyncJob, IntegrationConnector, Organization, Workspace, utcnow
from app.services.sync_orchestrator import (
    SYNC_JOB_QUEUED,
    SYNC_JOB_RUNNING,
    claim_next_connector_sync_job,
    enqueue_connector_sync_job,
)


class ConnectorSyncJobRecoveryTests(unittest.TestCase):
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
        db = self.SessionLocal()
        try:
            org = Organization(
                name="Sync Jobs Org",
                slug=f"sync-jobs-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
            )
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="General")
            db.add(workspace)
            db.flush()
            connector = IntegrationConnector(
                organization_id=org.id,
                connector_type="google-drive",
                nango_connection_id=f"conn-{uuid4().hex[:8]}",
                status="active",
            )
            db.add(connector)
            db.flush()
            self.organization_id = org.id
            self.workspace_id = workspace.id
            self.connector_id = connector.id
            db.commit()
        finally:
            db.close()

    def test_stale_running_job_is_requeued_and_claimable(self) -> None:
        db = self.SessionLocal()
        try:
            stale_started_at = utcnow() - timedelta(seconds=settings.connector_sync_job_stale_after_seconds + 60)
            stale_job = ConnectorSyncJob(
                connector_id=self.connector_id,
                organization_id=self.organization_id,
                workspace_id=self.workspace_id,
                status=SYNC_JOB_RUNNING,
                started_at=stale_started_at,
                attempt_count=1,
            )
            db.add(stale_job)
            db.commit()
            stale_job_id = stale_job.id

            job, created = enqueue_connector_sync_job(
                db,
                connector_id=self.connector_id,
                organization_id=self.organization_id,
                workspace_id=self.workspace_id,
                requested_by_user_id=None,
                full_sync=False,
            )

            self.assertFalse(created)
            self.assertEqual(job.id, stale_job_id)
            self.assertEqual(job.status, SYNC_JOB_QUEUED)
            self.assertIn("lease expired", job.error_message or "")

            claimed = claim_next_connector_sync_job(db)
            self.assertIsNotNone(claimed)
            assert claimed is not None
            self.assertEqual(claimed.id, stale_job_id)
            self.assertEqual(claimed.status, SYNC_JOB_RUNNING)
            self.assertEqual(claimed.attempt_count, 2)
            self.assertIsNone(claimed.error_message)
        finally:
            db.close()

    def test_fresh_running_job_still_blocks_duplicate_enqueue(self) -> None:
        db = self.SessionLocal()
        try:
            running_job = ConnectorSyncJob(
                connector_id=self.connector_id,
                organization_id=self.organization_id,
                workspace_id=self.workspace_id,
                status=SYNC_JOB_RUNNING,
                started_at=utcnow(),
                attempt_count=1,
            )
            db.add(running_job)
            db.commit()
            running_job_id = running_job.id

            job, created = enqueue_connector_sync_job(
                db,
                connector_id=self.connector_id,
                organization_id=self.organization_id,
                workspace_id=self.workspace_id,
                requested_by_user_id=None,
                full_sync=True,
            )

            self.assertFalse(created)
            self.assertEqual(job.id, running_job_id)
            self.assertEqual(job.status, SYNC_JOB_RUNNING)
            self.assertEqual(db.query(ConnectorSyncJob).count(), 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
