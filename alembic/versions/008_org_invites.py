"""Organization invite lifecycle support.

Revision ID: 008
Revises: 007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("invite_token_hash", sa.String(length=128), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organization_invites_organization_id"), "organization_invites", ["organization_id"], unique=False)
    op.create_index(op.f("ix_organization_invites_email"), "organization_invites", ["email"], unique=False)
    op.create_index(op.f("ix_organization_invites_status"), "organization_invites", ["status"], unique=False)
    op.create_index(op.f("ix_organization_invites_invite_token_hash"), "organization_invites", ["invite_token_hash"], unique=False)
    op.create_index(
        "ix_org_invites_org_email_status",
        "organization_invites",
        ["organization_id", "email", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_org_invites_org_email_status", table_name="organization_invites")
    op.drop_index(op.f("ix_organization_invites_invite_token_hash"), table_name="organization_invites")
    op.drop_index(op.f("ix_organization_invites_status"), table_name="organization_invites")
    op.drop_index(op.f("ix_organization_invites_email"), table_name="organization_invites")
    op.drop_index(op.f("ix_organization_invites_organization_id"), table_name="organization_invites")
    op.drop_table("organization_invites")
