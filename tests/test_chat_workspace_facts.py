import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models import (
    ChatSession,
    Document,
    DocumentChunk,
    DocumentPermission,
    DocumentStatus,
    Organization,
    OrganizationMembership,
    OrgMembershipRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from app.services.chat_workspace_facts import answer_workspace_fact_query, is_workspace_fact_query


def test_detects_workspace_fact_count_queries():
    assert is_workspace_fact_query("How many documents do we have in this workspace?")
    assert is_workspace_fact_query("number of indexed docs")
    assert is_workspace_fact_query("count files here")
    assert is_workspace_fact_query("how many chunks are indexed?")


def test_detects_workspace_fact_listing_queries():
    assert is_workspace_fact_query("what documents do we have?")
    assert is_workspace_fact_query("list documents in this workspace")
    assert is_workspace_fact_query("show documents")


def test_detects_workspace_fact_operational_queries():
    assert is_workspace_fact_query("How many documents were added this week?")
    assert is_workspace_fact_query("Show source breakdown for docs")
    assert is_workspace_fact_query("How many conversations do I have in this workspace?")
    assert is_workspace_fact_query("Which failed documents do we have?")
    assert is_workspace_fact_query("Are there stuck processing documents?")


def test_ignores_regular_semantic_questions():
    assert not is_workspace_fact_query("Summarize the retention policy.")
    assert not is_workspace_fact_query("What does checkpoint band 3 mean?")
    assert not is_workspace_fact_query("Explain conflicts of interest.")


class WorkspaceFactPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def test_full_rbac_facts_only_include_accessible_documents(self) -> None:
        db = self.SessionLocal()
        try:
            user = User(
                email="workspace-facts@example.com",
                password_hash="unused",
                full_name="Workspace Facts User",
                is_active=True,
                is_platform_owner=False,
            )
            organization = Organization(
                name="Workspace Facts Org",
                slug=f"workspace-facts-{uuid4().hex[:8]}",
                tenant_key=f"tenant-{uuid4().hex[:8]}",
            )
            db.add_all([user, organization])
            db.flush()

            workspace = Workspace(organization_id=organization.id, name="Restricted workspace")
            db.add(workspace)
            db.flush()
            db.add_all(
                [
                    OrganizationMembership(
                        user_id=user.id,
                        organization_id=organization.id,
                        role=OrgMembershipRole.member.value,
                    ),
                    WorkspaceMember(
                        user_id=user.id,
                        workspace_id=workspace.id,
                        role=WorkspaceMemberRole.member.value,
                    ),
                ]
            )

            accessible = Document(
                organization_id=organization.id,
                workspace_id=workspace.id,
                filename="visible.pdf",
                content_type="application/pdf",
                storage_path="inline://visible",
                source_type="pdf-upload",
                status=DocumentStatus.indexed.value,
            )
            restricted = Document(
                organization_id=organization.id,
                workspace_id=workspace.id,
                filename="restricted-payroll.pdf",
                content_type="application/pdf",
                storage_path="inline://restricted",
                source_type="google-drive-secret",
                status=DocumentStatus.failed.value,
            )
            db.add_all([accessible, restricted])
            db.flush()
            db.add_all(
                [
                    DocumentPermission(
                        document_id=accessible.id,
                        organization_id=organization.id,
                        user_id=user.id,
                        can_read=True,
                        source="test",
                        external_id="visible",
                    ),
                    DocumentChunk(
                        document_id=accessible.id,
                        chunk_index=0,
                        content="visible content",
                    ),
                    DocumentChunk(
                        document_id=restricted.id,
                        chunk_index=0,
                        content="restricted content",
                    ),
                ]
            )
            chat_session = ChatSession(
                organization_id=organization.id,
                workspace_id=workspace.id,
                user_id=user.id,
                title="Permission test",
            )
            db.add(chat_session)
            db.commit()

            with patch.object(settings, "rbac_mode", "full"):
                listing = answer_workspace_fact_query(
                    db,
                    chat_session,
                    user.id,
                    "list documents in this workspace",
                    user=user,
                )
                counts = answer_workspace_fact_query(
                    db,
                    chat_session,
                    user.id,
                    "count of documents with errors",
                    user=user,
                )
                chunks = answer_workspace_fact_query(
                    db,
                    chat_session,
                    user.id,
                    "how many chunks are indexed?",
                    user=user,
                )
                sources = answer_workspace_fact_query(
                    db,
                    chat_session,
                    user.id,
                    "show source breakdown for docs",
                    user=user,
                )

            self.assertIsNotNone(listing)
            self.assertIn("1 documents", listing[0])
            self.assertIn("visible.pdf", listing[0])
            self.assertNotIn("restricted-payroll.pdf", listing[0])
            self.assertEqual(counts[0], "This workspace has 0 failed documents.")
            self.assertEqual(chunks[0], "This workspace currently has 1 indexed chunks across 1 documents.")
            self.assertIn("pdf-upload: 1", sources[0])
            self.assertNotIn("google-drive-secret", sources[0])
        finally:
            db.close()
