"""add flow_id to a2a_tasks so a task read is scoped to its owning flow.

Revision ID: b7e4c1a9f2d3
Revises: a2c8f1e3b4d6
Create Date: 2026-06-26 13:00:00.000000

Phase: EXPAND

The column is added nullable with no backfill: the owning flow can't be reconstructed
from the stored task blob, so any row persisted before this migration keeps flow_id NULL
and reads back as not-found (the scoped read compares against the request's flow_id). This
is by design (fail-closed for the isolation fix), not data loss; a re-save repopulates
flow_id. The a2a_tasks table is one revision old, so few/no such rows exist in practice.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c1a9f2d3"  # pragma: allowlist secret
down_revision: str | None = "a2c8f1e3b4d6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("a2a_tasks", conn) and not migration.column_exists("a2a_tasks", "flow_id", conn):
        op.add_column("a2a_tasks", sa.Column("flow_id", sa.String(), nullable=True))


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("a2a_tasks", conn) and migration.column_exists("a2a_tasks", "flow_id", conn):
        op.drop_column("a2a_tasks", "flow_id")
