from __future__ import annotations

import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ConnectorSyncJob, IntegrationConnector, Organization, Workspace, utcnow
from app.services.sync_orchestrator import (
    STALE_SYNC_JOB_REQUEUE_MESSAGE,
    SYNC_JOB_QUEUED,
    SYNC_JOB_RUNNING,
    claim_next_connector_sync_job,
    enqueue_connector_sync_job,
    requeue_stale_connector_sync_jobs,
)


class ConnectorSyncJobOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.SessionLocal()
        try:
            org = Organization(name="Org", slug="org", tenant_key="tenant", status="active", plan="free_trial")
            db.add(org)
            db.flush()
            workspace = Workspace(organization_id=org.id, name="Workspace")
            connector = IntegrationConnector(
                organization_id=org.id,
                connector_type="google-drive",
                nango_connection_id="conn",
                status="active",
            )
            db.add_all([workspace, connector])
            db.commit()
            self.org_id = org.id
            self.workspace_id = workspace.id
            self.connector_id = connector.id
        finally:
            db.close()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_active_connector_job_blocks_all_workspace_scopes(self) -> None:
        db = self.SessionLocal()
        try:
            org_job, created = enqueue_connector_sync_job(
                db,
                connector_id=self.connector_id,
                organization_id=self.org_id,
                workspace_id=None,
                requested_by_user_id=None,
                full_sync=False,
            )
            self.assertTrue(created)

            scoped_job, scoped_created = enqueue_connector_sync_job(
                db,
                connector_id=self.connector_id,
                organization_id=self.org_id,
                workspace_id=self.workspace_id,
                requested_by_user_id=None,
                full_sync=False,
            )

            self.assertFalse(scoped_created)
            self.assertEqual(scoped_job.id, org_job.id)
            self.assertEqual(db.query(ConnectorSyncJob).count(), 1)
        finally:
            db.close()

    def test_stale_running_jobs_are_requeued(self) -> None:
        db = self.SessionLocal()
        try:
            job = ConnectorSyncJob(
                connector_id=self.connector_id,
                organization_id=self.org_id,
                workspace_id=self.workspace_id,
                status=SYNC_JOB_RUNNING,
                started_at=utcnow() - timedelta(minutes=30),
                attempt_count=1,
            )
            db.add(job)
            db.commit()

            count = requeue_stale_connector_sync_jobs(db, stale_after_seconds=60)

            self.assertEqual(count, 1)
            db.refresh(job)
            self.assertEqual(job.status, SYNC_JOB_QUEUED)
            self.assertEqual(job.error_message, STALE_SYNC_JOB_REQUEUE_MESSAGE)
        finally:
            db.close()

    def test_claim_skips_queued_job_when_same_connector_is_running(self) -> None:
        db = self.SessionLocal()
        try:
            db.add(
                ConnectorSyncJob(
                    connector_id=self.connector_id,
                    organization_id=self.org_id,
                    workspace_id=None,
                    status=SYNC_JOB_RUNNING,
                    started_at=utcnow(),
                    attempt_count=1,
                )
            )
            db.add(
                ConnectorSyncJob(
                    connector_id=self.connector_id,
                    organization_id=self.org_id,
                    workspace_id=self.workspace_id,
                    status=SYNC_JOB_QUEUED,
                )
            )
            db.commit()

            self.assertIsNone(claim_next_connector_sync_job(db))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

