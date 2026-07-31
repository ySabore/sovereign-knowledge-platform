from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.models import IntegrationConnector, Organization, Workspace
from app.services import sync_orchestrator


class _FakeDb:
    def __init__(self, *, connector: SimpleNamespace, organization: SimpleNamespace, workspace: SimpleNamespace) -> None:
        self.connector = connector
        self.organization = organization
        self.workspace = workspace
        self.commits = 0

    def get(self, model: object, row_id: object) -> SimpleNamespace | None:
        if model is IntegrationConnector and row_id == self.connector.id:
            return self.connector
        if model is Organization and row_id == self.organization.id:
            return self.organization
        if model is Workspace and row_id == self.workspace.id:
            return self.workspace
        return None

    def commit(self) -> None:
        self.commits += 1


class SyncOrchestratorScopeTests(unittest.TestCase):
    def test_google_drive_sync_without_effective_folder_scope_fails_before_fetch(self) -> None:
        org_id = uuid4()
        workspace_id = uuid4()
        connector = SimpleNamespace(
            id=uuid4(),
            organization_id=org_id,
            connector_type="google-drive",
            nango_connection_id="conn",
            config={
                "workspace_id": str(workspace_id),
                "workspace_ids": [str(workspace_id)],
                "workspace_settings": {
                    str(workspace_id): {
                        "drive_folder_ids": [],
                        "drive_include_subfolders": True,
                    }
                },
            },
            status="active",
            last_synced_at=None,
            document_count=0,
        )
        db = _FakeDb(
            connector=connector,
            organization=SimpleNamespace(id=org_id),
            workspace=SimpleNamespace(id=workspace_id, organization_id=org_id),
        )

        with patch.object(sync_orchestrator, "fetch_documents", side_effect=AssertionError("fetch should not run")):
            result = sync_orchestrator.run_connector_sync(db, connector.id, workspace_id_override=workspace_id)

        self.assertEqual(result["status"], "error")
        self.assertIn("Google Drive folder scope is required", result["detail"])
        self.assertEqual(db.commits, 0)
        self.assertEqual(connector.status, "active")

    def test_stale_workspace_sync_fails_when_connector_scope_was_removed(self) -> None:
        org_id = uuid4()
        workspace_id = uuid4()
        other_workspace_id = uuid4()
        connector = SimpleNamespace(
            id=uuid4(),
            organization_id=org_id,
            connector_type="notion",
            nango_connection_id="conn",
            config={"workspace_ids": [str(other_workspace_id)], "workspace_id": str(other_workspace_id)},
            status="active",
            last_synced_at=None,
            document_count=0,
        )
        db = _FakeDb(
            connector=connector,
            organization=SimpleNamespace(id=org_id),
            workspace=SimpleNamespace(id=workspace_id, organization_id=org_id),
        )

        with patch.object(sync_orchestrator, "fetch_documents", side_effect=AssertionError("fetch should not run")):
            result = sync_orchestrator.run_connector_sync(db, connector.id, workspace_id_override=workspace_id)

        self.assertEqual(result, {"status": "error", "detail": "Connector is not enabled for this workspace"})
        self.assertEqual(db.commits, 0)

    def test_google_drive_sync_with_workspace_folder_scope_can_reach_nango_readiness_check(self) -> None:
        org_id = uuid4()
        workspace_id = uuid4()
        connector = SimpleNamespace(
            id=uuid4(),
            organization_id=org_id,
            connector_type="google-drive",
            nango_connection_id="conn",
            config={
                "workspace_id": str(workspace_id),
                "workspace_ids": [str(workspace_id)],
                "workspace_settings": {
                    str(workspace_id): {
                        "drive_folder_ids": ["folder_123"],
                        "drive_include_subfolders": True,
                    }
                },
            },
            status="active",
            last_synced_at=None,
            document_count=0,
        )
        db = _FakeDb(
            connector=connector,
            organization=SimpleNamespace(id=org_id),
            workspace=SimpleNamespace(id=workspace_id, organization_id=org_id),
        )

        with patch.object(sync_orchestrator, "nango_configured", return_value=False):
            result = sync_orchestrator.run_connector_sync(db, connector.id, workspace_id_override=workspace_id)

        self.assertEqual(result["status"], "skipped")
        self.assertIn("NANGO_SECRET_KEY", result["detail"])


if __name__ == "__main__":
    unittest.main()
