"""Stripe customer/subscription fields + organization_connectors for plan limits.

Revision ID: 005
Revises: 004

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("billing_grace_until", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "organization_connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_key", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "integration_key", name="uq_org_connector_integration"),
    )
    op.create_index(
        op.f("ix_organization_connectors_organization_id"),
        "organization_connectors",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_connectors_organization_id"), table_name="organization_connectors")
    op.drop_table("organization_connectors")
    op.drop_column("organizations", "billing_grace_until")
    op.drop_column("organizations", "stripe_subscription_id")
    op.drop_column("organizations", "stripe_customer_id")
