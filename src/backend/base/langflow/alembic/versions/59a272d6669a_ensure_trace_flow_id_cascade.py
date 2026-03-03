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

from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "59a272d6669a"  # pragma: allowlist secret
down_revision: str | None = "3478f0bd6ccb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Only proceed if trace table exists
    if not migration.table_exists("trace", conn):
        return

    # Use batch mode for SQLite compatibility
    # This recreates the table with the correct FK constraint
    with op.batch_alter_table("trace", schema=None) as batch_op:
        # Drop existing FK constraint (name may vary by database)
        # batch_alter_table handles this gracefully
        batch_op.drop_constraint("fk_trace_flow_id_flow", type_="foreignkey")

        # Recreate FK with ondelete CASCADE
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

    # Revert to FK without CASCADE (though this is not recommended)
    with op.batch_alter_table("trace", schema=None) as batch_op:
        batch_op.drop_constraint("fk_trace_flow_id_flow", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_trace_flow_id_flow",
            "flow",
            ["flow_id"],
            ["id"],
        )
