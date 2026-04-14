"""Per-organization encrypted cloud LLM credentials and API base overrides.

Revision ID: 010
Revises: 009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("anthropic_api_key_encrypted", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("openai_api_base_url", sa.String(length=512), nullable=True))
    op.add_column("organizations", sa.Column("anthropic_api_base_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "anthropic_api_base_url")
    op.drop_column("organizations", "openai_api_base_url")
    op.drop_column("organizations", "anthropic_api_key_encrypted")
    op.drop_column("organizations", "openai_api_key_encrypted")
