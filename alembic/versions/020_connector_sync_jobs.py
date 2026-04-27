"""Add durable connector sync job queue table.

Revision ID: 020
Revises: 019
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connector_sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_sync", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("documents_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_connector_sync_jobs_connector_id"), "connector_sync_jobs", ["connector_id"], unique=False)
    op.create_index(
        op.f("ix_connector_sync_jobs_organization_id"), "connector_sync_jobs", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_connector_sync_jobs_status"), "connector_sync_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_connector_sync_jobs_workspace_id"), "connector_sync_jobs", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_connector_sync_jobs_workspace_id"), table_name="connector_sync_jobs")
    op.drop_index(op.f("ix_connector_sync_jobs_status"), table_name="connector_sync_jobs")
    op.drop_index(op.f("ix_connector_sync_jobs_organization_id"), table_name="connector_sync_jobs")
    op.drop_index(op.f("ix_connector_sync_jobs_connector_id"), table_name="connector_sync_jobs")
    op.drop_table("connector_sync_jobs")

