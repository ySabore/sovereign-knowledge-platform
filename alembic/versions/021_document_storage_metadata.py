"""Add storage metadata columns to documents.

Revision ID: 021
Revises: 020
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("storage_provider", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("storage_bucket", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("storage_key", sa.String(length=1024), nullable=True))
    op.add_column("documents", sa.Column("storage_size_bytes", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("storage_etag", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "storage_etag")
    op.drop_column("documents", "storage_size_bytes")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "storage_bucket")
    op.drop_column("documents", "storage_provider")

