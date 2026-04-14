"""Document ACL + organization billing plan for RBAC and rate tiers.

Revision ID: 004
Revises: 003
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("plan", sa.String(length=32), server_default="free_trial", nullable=False))

    op.create_table(
        "document_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("can_read", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "source", "external_id", name="uq_document_permission_source_ext"),
    )
    op.create_index("ix_document_permissions_org_user", "document_permissions", ["organization_id", "user_id"])
    op.create_index("ix_document_permissions_document_id", "document_permissions", ["document_id"])
    op.create_index("ix_document_permissions_connector_id", "document_permissions", ["connector_id"])


def downgrade() -> None:
    op.drop_table("document_permissions")
    op.drop_column("organizations", "plan")
