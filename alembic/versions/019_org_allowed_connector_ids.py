"""Add per-organization connector allowlist.

Revision ID: 019
Revises: 018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("allowed_connector_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "allowed_connector_ids")
