"""Add ondelete CASCADE to span.trace_id FK

Revision ID: 83cd04b12a34
Revises: 0e6138e7a0c2
Create Date: 2026-03-29 12:00:00.000000

Phase: EXPAND

The original migration (3478f0bd6ccb) created the span.trace_id foreign key
without ondelete="CASCADE". This causes a ForeignKeyViolation when deleting
flows that have associated traces, because the cascade chain
flow -> trace -> span is broken at the trace -> span link.

See: https://github.com/langflow-ai/langflow/issues/12346
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "83cd04b12a34"  # pragma: allowlist secret
down_revision: str | None = "0e6138e7a0c2"  # pragma: allowlist secret
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

    if not migration.table_exists("span", conn):
        return

    fk_name = _get_fk_constraint_name(conn, "span", "trace_id")

    if fk_name is None:
        # No FK exists, create one with CASCADE
        with op.batch_alter_table("span", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_span_trace_id_trace",
                "trace",
                ["trace_id"],
                ["id"],
                ondelete="CASCADE",
            )
    else:
        # FK exists, recreate it with CASCADE
        with op.batch_alter_table("span", schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_span_trace_id_trace",
                "trace",
                ["trace_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    fk_name = _get_fk_constraint_name(conn, "span", "trace_id")

    if fk_name is None:
        return

    # Revert to FK without CASCADE
    with op.batch_alter_table("span", schema=None) as batch_op:
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            None,  # Let database auto-generate name
            "trace",
            ["trace_id"],
            ["id"],
        )
