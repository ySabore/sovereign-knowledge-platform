"""Connector sync must rollback after a failed ingest so later docs still write."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    IntegrationConnector,
    Organization,
    OrgStatus,
    Workspace,
)
from app.services.nango_client import DocumentFetchResult
from app.services.sync_orchestrator import run_connector_sync


class SyncIngestRollbackTests(unittest.TestCase):
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
            org = Organization(
                name="Sync Org",
                slug=f"sync-org-{uuid4().hex[:8]}",
                tenant_key=uuid4().hex,
                status=OrgStatus.active.value,
                plan="free",
            )
            db.add(org)
            db.flush()
            ws = Workspace(organization_id=org.id, name="General")
            db.add(ws)
            db.flush()
            conn = IntegrationConnector(
                organization_id=org.id,
                connector_type="confluence",
                nango_connection_id="nango-sync-1",
                status="active",
                config={"workspace_id": str(ws.id)},
            )
            db.add(conn)
            db.commit()
            self.org_id = org.id
            self.workspace_id = ws.id
            self.connector_id = conn.id
        finally:
            db.close()

    def test_failed_ingest_does_not_poison_remaining_documents(self) -> None:
        docs = [
            DocumentFetchResult(
                external_id="page-1",
                name="One",
                content="alpha content",
                url="https://example.com/1",
                last_modified=None,
                metadata={},
            ),
            DocumentFetchResult(
                external_id="page-2",
                name="Two",
                content="beta content",
                url="https://example.com/2",
                last_modified=None,
                metadata={},
            ),
            DocumentFetchResult(
                external_id="page-3",
                name="Three",
                content="gamma content",
                url="https://example.com/3",
                last_modified=None,
                metadata={},
            ),
        ]
        calls: list[str] = []

        def fake_ingest(db, params):
            calls.append(params.external_id)
            if params.external_id == "page-2":
                # Simulate a DB error that aborts the current transaction.
                raise IntegrityError("duplicate", {}, Exception("duplicate"))
            return uuid4(), 1

        db = self.SessionLocal()
        try:
            with patch("app.services.sync_orchestrator.nango_configured", return_value=True), patch(
                "app.services.sync_orchestrator.fetch_documents",
                return_value=(docs, None),
            ), patch(
                "app.services.sync_orchestrator.ingest_document",
                side_effect=fake_ingest,
            ):
                result = run_connector_sync(db, self.connector_id, full_sync=False)
        finally:
            db.close()

        self.assertEqual(result.get("status"), "ok")
        self.assertEqual(calls, ["page-1", "page-2", "page-3"])
        self.assertEqual(result.get("documents_ingested"), 2)
        self.assertTrue(any("page-2" in e for e in result.get("errors") or []))


if __name__ == "__main__":
    unittest.main()
