"""Store confidence and generation mode on assistant chat messages.

Revision ID: 018
Revises: 017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("confidence", sa.String(length=32), nullable=True))
    op.add_column("chat_messages", sa.Column("generation_mode", sa.String(length=64), nullable=True))
    op.add_column("chat_messages", sa.Column("generation_model", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "generation_model")
    op.drop_column("chat_messages", "generation_mode")
    op.drop_column("chat_messages", "confidence")
