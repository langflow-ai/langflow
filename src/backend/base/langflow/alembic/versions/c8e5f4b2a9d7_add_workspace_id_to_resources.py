"""add nullable workspace_id column to flow, folder, deployment

Revision ID: c8e5f4b2a9d7
Revises: f7a8b9c0d1e2
Create Date: 2026-05-19

Phase: EXPAND

Adds a nullable ``workspace_id`` UUID column (no foreign key — there is no
``workspace`` table in OSS yet) to ``flow``, ``folder``, and ``deployment`` so
the authorization layer can pass ``workspace:{workspace_id}`` as the Casbin
domain. Existing rows stay NULL; the enterprise plugin or a future workspace
admin API will populate it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "c8e5f4b2a9d7"  # pragma: allowlist secret
down_revision: str | None = "f7a8b9c0d1e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = ("flow", "folder", "deployment")


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            if not migration.column_exists(table_name=table, column_name="workspace_id", conn=conn):
                batch_op.add_column(sa.Column("workspace_id", sa.Uuid(), nullable=True))
                batch_op.create_index(f"ix_{table}_workspace_id", ["workspace_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            if migration.column_exists(table_name=table, column_name="workspace_id", conn=conn):
                batch_op.drop_index(f"ix_{table}_workspace_id")
                batch_op.drop_column("workspace_id")
