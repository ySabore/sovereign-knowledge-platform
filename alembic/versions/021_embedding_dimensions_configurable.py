"""Align document chunk vector schema with configured embedding dimensions.

Revision ID: 021
Revises: 020
"""

from typing import Sequence, Union

import pgvector.sqlalchemy
from alembic import op

from app.config import settings

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _embedding_dimensions() -> int:
    return int(settings.embedding_dimensions)


def _retype_embedding_column(dimensions: int) -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_cosine")
    op.alter_column(
        "document_chunks",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(768),
        type_=pgvector.sqlalchemy.Vector(dimensions),
        existing_nullable=True,
        postgresql_using=f"embedding::vector({dimensions})",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_cosine "
        "ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def upgrade() -> None:
    _retype_embedding_column(_embedding_dimensions())


def downgrade() -> None:
    _retype_embedding_column(768)
