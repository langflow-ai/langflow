"""add flow history_paused

Revision ID: b7d1f3a5c9e2
Revises: f4b8c2d6e9a1
Create Date: 2026-10-19

Phase: EXPAND
Safe to rollback: YES (one column with a default; downgrade drops it).
Services compatible: All versions while flow history is off, which is the
    default. Older backends never read the column, and newer backends record no
    history while it is off. Turn flow history on only after every Langflow
    backend that uses this database runs this version: an older backend writes
    flow.data without recording it, and without setting this mark.

``flow.history_paused`` marks a flow whose graph was written while flow history
was off, after its history had started. Its next recorded write starts the
history again from a new checkpoint instead of refusing the write because the
stored graph no longer matches its recorded revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b7d1f3a5c9e2"  # pragma: allowlist secret
down_revision: str | None = "f4b8c2d6e9a1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.column_exists(table_name="flow", column_name="history_paused", conn=conn):
        with op.batch_alter_table("flow", schema=None) as batch_op:
            batch_op.add_column(sa.Column("history_paused", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    conn = op.get_bind()
    if migration.column_exists(table_name="flow", column_name="history_paused", conn=conn):
        with op.batch_alter_table("flow", schema=None) as batch_op:
            batch_op.drop_column("history_paused")
