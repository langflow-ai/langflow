"""Ensure trace.flow_id foreign key has ondelete CASCADE

Revision ID: 59a272d6669a
Revises: 3478f0bd6ccb
Create Date: 2026-03-03 12:00:00.000000

Phase: EXPAND

This is a defensive migration to ensure the trace.flow_id foreign key
has ondelete="CASCADE". The original migration (3478f0bd6ccb) already
creates it with CASCADE, but this ensures consistency for any databases
that may have gotten into an inconsistent state.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "59a272d6669a"  # pragma: allowlist secret
down_revision: str | None = "3478f0bd6ccb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_fk_constraint_name(conn, table_name: str, column_name: str) -> str | None:
    """Find the foreign key constraint name for a given column."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk["name"]
    return None


def upgrade() -> None:
    conn = op.get_bind()

    # Only proceed if trace table exists
    if not migration.table_exists("trace", conn):
        return

    # Find the actual FK constraint name (it may vary by database)
    fk_name = _get_fk_constraint_name(conn, "trace", "flow_id")

    if fk_name is None:
        # No FK exists, create one with CASCADE
        with op.batch_alter_table("trace", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_trace_flow_id_flow",
                "flow",
                ["flow_id"],
                ["id"],
                ondelete="CASCADE",
            )
    else:
        # FK exists, recreate it with CASCADE using the correct name
        with op.batch_alter_table("trace", schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_trace_flow_id_flow",
                "flow",
                ["flow_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("trace", conn):
        return

    fk_name = _get_fk_constraint_name(conn, "trace", "flow_id")

    if fk_name is None:
        return

    # Revert to FK without CASCADE (though this is not recommended)
    with op.batch_alter_table("trace", schema=None) as batch_op:
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            None,  # Let database auto-generate name
            "flow",
            ["flow_id"],
            ["id"],
        )
