"""Organization description and per-org chat LLM preferences.

Revision ID: 009
Revises: 008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("preferred_chat_provider", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("preferred_chat_model", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "preferred_chat_model")
    op.drop_column("organizations", "preferred_chat_provider")
    op.drop_column("organizations", "description")
