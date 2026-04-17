"""Add actor_role to audit_logs for compliance-style audit trails.

Revision ID: 015
Revises: 014
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("actor_role", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_audit_logs_actor_role", "audit_logs", ["actor_role"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_role", table_name="audit_logs")
    op.drop_column("audit_logs", "actor_role")
