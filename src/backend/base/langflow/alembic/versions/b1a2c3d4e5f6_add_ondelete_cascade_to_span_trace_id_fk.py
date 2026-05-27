"""Add ondelete CASCADE to span.trace_id foreign key

Revision ID: b1a2c3d4e5f6
Revises: fc7f696a57bf
Create Date: 2026-05-27 12:00:00.000000

Phase: EXPAND

This ensures that when a trace is deleted, all associated spans are
automatically deleted. The model layer (traces/model.py line 291) already
has ondelete="CASCADE", but existing PostgreSQL databases need this
migration to update the constraint.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | None = "fc7f696a57bf"  # pragma: allowlist secret
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
        with op.batch_alter_table("span", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_span_trace_id_trace",
                "trace",
                ["trace_id"],
                ["id"],
                ondelete="CASCADE",
            )
    else:
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

    with op.batch_alter_table("span", schema=None) as batch_op:
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            None,  # Let database auto-generate name
            "trace",
            ["trace_id"],
            ["id"],
        )
