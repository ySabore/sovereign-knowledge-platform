"""Add storage metadata columns to documents.

Revision ID: 022
Revises: 021
"""

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

from app.config import settings

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _existing_columns(table_name):
        op.add_column(table_name, column)


def _drop_column_if_present(table_name: str, column_name: str) -> None:
    if column_name in _existing_columns(table_name):
        op.drop_column(table_name, column_name)


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
    _add_column_if_missing("documents", sa.Column("storage_provider", sa.String(length=32), nullable=True))
    _add_column_if_missing("documents", sa.Column("storage_bucket", sa.String(length=255), nullable=True))
    _add_column_if_missing("documents", sa.Column("storage_key", sa.String(length=1024), nullable=True))
    _add_column_if_missing("documents", sa.Column("storage_size_bytes", sa.Integer(), nullable=True))
    _add_column_if_missing("documents", sa.Column("storage_etag", sa.String(length=128), nullable=True))

    # The previous duplicate 021 revisions allowed either half to be recorded as applied.
    # Re-applying this cast lets databases that only ran the storage half converge.
    _retype_embedding_column(_embedding_dimensions())


def downgrade() -> None:
    _retype_embedding_column(768)
    _drop_column_if_present("documents", "storage_etag")
    _drop_column_if_present("documents", "storage_size_bytes")
    _drop_column_if_present("documents", "storage_key")
    _drop_column_if_present("documents", "storage_bucket")
    _drop_column_if_present("documents", "storage_provider")

