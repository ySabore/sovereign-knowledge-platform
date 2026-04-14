"""Document source metadata + chunk section titles (Component 3.3).

Revision ID: 006
Revises: 005

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_type", sa.String(length=64), server_default="pdf-upload", nullable=False))
    op.add_column("documents", sa.Column("external_id", sa.String(length=512), nullable=True))
    op.add_column("documents", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.add_column("documents", sa.Column("ingestion_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column("documents", sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("document_chunks", sa.Column("section_title", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE documents
        SET source_type = 'pdf-upload',
            external_id = id::text
        WHERE external_id IS NULL;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_org_source_external
        ON documents (organization_id, source_type, external_id)
        WHERE external_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_org_source_external")
    op.drop_column("document_chunks", "section_title")
    op.drop_column("documents", "last_indexed_at")
    op.drop_column("documents", "ingestion_metadata")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "external_id")
    op.drop_column("documents", "source_type")
