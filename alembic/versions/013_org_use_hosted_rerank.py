"""Optional Cohere hosted rerank for heuristic/hybrid retrieval.

Revision ID: 013
Revises: 012
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("use_hosted_rerank", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("organizations", "use_hosted_rerank", server_default=None)


def downgrade() -> None:
    op.drop_column("organizations", "use_hosted_rerank")
