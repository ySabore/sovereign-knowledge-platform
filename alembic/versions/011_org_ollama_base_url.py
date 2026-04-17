"""Optional per-organization Ollama base URL (self-hosted LLM).

Revision ID: 011
Revises: 010
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("ollama_base_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "ollama_base_url")
