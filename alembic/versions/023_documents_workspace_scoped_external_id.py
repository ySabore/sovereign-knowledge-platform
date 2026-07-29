"""Scope document external_id uniqueness to workspace.

Revision ID: 023
Revises: 022

The previous unique index was (organization_id, source_type, external_id), so
connector sync / ingest-text in one workspace could overwrite another workspace's
document that shared the same source external id. Identity is now workspace-scoped.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_org_source_external")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_org_workspace_source_external
        ON documents (organization_id, workspace_id, source_type, external_id)
        WHERE external_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_org_workspace_source_external")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_org_source_external
        ON documents (organization_id, source_type, external_id)
        WHERE external_id IS NOT NULL;
        """
    )
