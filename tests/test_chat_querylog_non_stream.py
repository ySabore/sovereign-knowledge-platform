from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("AUDIT_HTTP_MIDDLEWARE_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models import ChatSession, Organization, OrganizationMembership, OrgMembershipRole, OrgStatus, QueryLog, User, Workspace, WorkspaceMember, WorkspaceMemberRole
from app.services.metrics import build_metrics_summary


class ChatQueryLogNonStreamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        app = create_app()

        def override_get_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._seed()

    def _seed(self) -> None:
        db = self.SessionLocal()
        try:
            user = User(
                email="querylog-non-stream@example.com",
                password_hash=hash_password("ChangeMeNow!"),
                full_name="Query Log User",
                is_active=True,
                is_platform_owner=False,
            )
            db.add(user)
            db.flush()
            self.user_id = user.id

            org = Organization(
                name="QueryLog Org",
                slug=f"querylog-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
                status=OrgStatus.active.value,
            )
            db.add(org)
            db.flush()
            self.org_id = org.id

            workspace = Workspace(organization_id=org.id, name="General", description="Query log workspace")
            db.add(workspace)
            db.flush()
            self.workspace_id = workspace.id

            db.add(
                OrganizationMembership(
                    user_id=user.id,
                    organization_id=org.id,
                    role=OrgMembershipRole.member.value,
                )
            )
            db.add(
                WorkspaceMember(
                    user_id=user.id,
                    workspace_id=workspace.id,
                    role=WorkspaceMemberRole.member.value,
                )
            )
            db.flush()

            session = ChatSession(
                organization_id=org.id,
                workspace_id=workspace.id,
                user_id=user.id,
                title="Query log test",
            )
            db.add(session)
            db.flush()
            self.session_id = session.id
            db.commit()
        finally:
            db.close()

    def _login(self) -> dict[str, str]:
        resp = self.client.post("/auth/login", json={"email": "querylog-non-stream@example.com", "password": "ChangeMeNow!"})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_non_stream_chat_turn_persists_query_log_and_metrics(self) -> None:
        headers = self._login()
        question = "How many documents are in this workspace?"
        with patch(
            "app.routers.chat.answer_workspace_fact_query",
            return_value=("There are 3 indexed documents.", [], "workspace_fact"),
        ), patch("app.routers.chat.enforce_org_query_limits", return_value=None):
            resp = self.client.post(
                f"/chat/sessions/{self.session_id}/messages",
                headers=headers,
                json={"content": question},
            )
        self.assertEqual(resp.status_code, 201, resp.text)

        db = self.SessionLocal()
        try:
            rows = db.query(QueryLog).filter(QueryLog.organization_id == self.org_id).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].question, question)
            self.assertEqual(rows[0].answer, "There are 3 indexed documents.")
            with patch("app.services.metrics.func.date_trunc", side_effect=lambda _part, col: func.date(col)):
                metrics = build_metrics_summary(db, organization_id=self.org_id)
            self.assertEqual(int(metrics["totals"]["queries_this_month"]), 1)
            self.assertTrue(any(item.get("text") == question for item in metrics.get("top_queries", [])))
        finally:
            db.close()

    def test_api_chat_stream_alias_persists_query_log_and_metrics(self) -> None:
        headers = self._login()
        question = "What is in this workspace via stream alias?"
        with patch(
            "app.services.chat_sse.answer_workspace_fact_query",
            return_value=("Streamed workspace fact answer.", [], "workspace_fact"),
        ), patch("app.routers.api_chat.enforce_org_query_limits", return_value=None):
            resp = self.client.post(
                "/chat",
                headers=headers,
                json={"session_id": str(self.session_id), "content": question, "top_k": 5},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn('"type": "done"', resp.text)

        db = self.SessionLocal()
        try:
            rows = (
                db.query(QueryLog)
                .filter(QueryLog.organization_id == self.org_id, QueryLog.question == question)
                .all()
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].answer, "Streamed workspace fact answer.")
            with patch("app.services.metrics.func.date_trunc", side_effect=lambda _part, col: func.date(col)):
                metrics = build_metrics_summary(db, organization_id=self.org_id)
            self.assertEqual(int(metrics["totals"]["queries_this_month"]), 1)
            self.assertTrue(any(item.get("text") == question for item in metrics.get("top_queries", [])))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

