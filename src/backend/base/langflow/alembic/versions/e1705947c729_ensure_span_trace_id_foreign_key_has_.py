"""Ensure span.trace_id foreign key has ondelete CASCADE

Revision ID: e1705947c729
Revises: b7c4d8e9f012
Create Date: 2026-07-03 11:59:20.247447

Phase: EXPAND

Fixes https://github.com/langflow-ai/langflow/issues/13955.

The original migration (3478f0bd6ccb) created the span.trace_id foreign
key without ondelete="CASCADE". "Clear all" traces (DELETE /api/v1/traces)
issues a bulk `DELETE FROM trace WHERE flow_id = ...` that bypasses the
ORM's `cascade="all, delete-orphan"` relationship (which only fires via
session.delete()), so the database rejected the delete with a foreign key
violation whenever a trace still had spans referencing it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e1705947c729"  # pragma: allowlist secret
down_revision: str | None = "b7c4d8e9f012"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# SQLite never persists a name for an inline/anonymous FK constraint (reflection
# reports name=None), so batch_alter_table can't target it by name unless we give
# it a naming_convention to derive one deterministically for the reflected table.
_FK_NAME = "fk_span_trace_id_trace"
_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _find_trace_id_fk(conn) -> dict | None:
    """Return the span.trace_id foreign key's reflected info, or None if absent."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys("span"):
        if "trace_id" in fk["constrained_columns"]:
            return fk
    return None


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    fk = _find_trace_id_fk(conn)
    if fk is not None and (fk.get("options") or {}).get("ondelete", "").upper() == "CASCADE":
        return  # Already correct.

    with op.batch_alter_table("span", schema=None, naming_convention=_NAMING_CONVENTION) as batch_op:
        if fk is not None:
            batch_op.drop_constraint(fk["name"] or _FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            "trace",
            ["trace_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    fk = _find_trace_id_fk(conn)
    if fk is None:
        return

    with op.batch_alter_table("span", schema=None, naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(fk["name"] or _FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            None,
            "trace",
            ["trace_id"],
            ["id"],
        )
