from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.routers import connectors


class _FakeDb:
    def __init__(self, connector: SimpleNamespace) -> None:
        self.connector = connector
        self.executed = False
        self.committed = False

    def get(self, _model: object, connector_id: object) -> SimpleNamespace | None:
        if connector_id == self.connector.id:
            return self.connector
        return None

    def execute(self, _statement: object) -> None:
        self.executed = True

    def commit(self) -> None:
        self.committed = True


class ConnectorBillingCleanupTests(unittest.TestCase):
    def test_delete_connector_unregisters_plan_usage(self) -> None:
        org_id = uuid4()
        connector_id = uuid4()
        conn = SimpleNamespace(id=connector_id, organization_id=org_id, connector_type="google-drive")
        db = _FakeDb(conn)
        user = SimpleNamespace(id=uuid4(), is_platform_owner=False)

        with patch.object(connectors, "_require_connector_manage_access"), patch.object(
            connectors, "_write_audit_log"
        ), patch.object(connectors, "invalidate_plan_cache"), patch.object(
            connectors, "unregister_connector_integration"
        ) as unregister:
            connectors.delete_integration_connector(connector_id, db=db, user=user)

        unregister.assert_called_once_with(db, org_id, "google-drive")
        self.assertTrue(db.executed)
        self.assertTrue(db.committed)

    def test_remove_last_workspace_unregisters_plan_usage(self) -> None:
        org_id = uuid4()
        connector_id = uuid4()
        workspace_id = uuid4()
        conn = SimpleNamespace(
            id=connector_id,
            organization_id=org_id,
            connector_type="google-drive",
            config={"workspace_ids": [str(workspace_id)], "workspace_id": str(workspace_id)},
        )
        db = _FakeDb(conn)
        user = SimpleNamespace(id=uuid4(), is_platform_owner=False)

        with patch.object(connectors, "_require_workspace_connector_manage_access"), patch.object(
            connectors, "_write_audit_log"
        ), patch.object(connectors, "invalidate_plan_cache"), patch.object(
            connectors, "unregister_connector_integration"
        ) as unregister:
            connectors.remove_connector_from_workspace(connector_id, workspace_id, db=db, user=user)

        unregister.assert_called_once_with(db, org_id, "google-drive")
        self.assertTrue(db.executed)
        self.assertTrue(db.committed)


if __name__ == "__main__":
    unittest.main()
