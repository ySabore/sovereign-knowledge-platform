"""Nango-backed connectors + query audit log (Layer 5 / 3.4).

Revision ID: 007
Revises: 006

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("clerk_organization_id", sa.String(length=255), nullable=True))
    op.create_index(
        op.f("ix_organizations_clerk_organization_id"),
        "organizations",
        ["clerk_organization_id"],
        unique=True,
    )

    op.create_table(
        "connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_type", sa.String(length=128), nullable=False),
        sa.Column("nango_connection_id", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "connector_type", name="uq_connectors_org_type"),
    )
    op.create_index(op.f("ix_connectors_organization_id"), "connectors", ["organization_id"], unique=False)

    op.add_column(
        "documents",
        sa.Column("integration_connector_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_integration_connector_id",
        "documents",
        "connectors",
        ["integration_connector_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_documents_integration_connector_id"),
        "documents",
        ["integration_connector_id"],
        unique=False,
    )

    op.create_table(
        "query_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("citations_json", postgresql.JSON(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_query_logs_org_workspace_created",
        "query_logs",
        ["organization_id", "workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_query_logs_org_created",
        "query_logs",
        ["organization_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_query_logs_org_created", table_name="query_logs")
    op.drop_index("ix_query_logs_org_workspace_created", table_name="query_logs")
    op.drop_table("query_logs")

    op.drop_index(op.f("ix_documents_integration_connector_id"), table_name="documents")
    op.drop_constraint("fk_documents_integration_connector_id", "documents", type_="foreignkey")
    op.drop_column("documents", "integration_connector_id")

    op.drop_index(op.f("ix_connectors_organization_id"), table_name="connectors")
    op.drop_table("connectors")

    op.drop_index(op.f("ix_organizations_clerk_organization_id"), table_name="organizations")
    op.drop_column("organizations", "clerk_organization_id")
