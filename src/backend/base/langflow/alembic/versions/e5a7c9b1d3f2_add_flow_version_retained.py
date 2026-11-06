"""Add retained flag to flow_version.

Revision ID: e5a7c9b1d3f2
Revises: c4d8e2f6a1b7
Create Date: 2026-10-07

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e5a7c9b1d3f2"  # pragma: allowlist secret -- migration revision identifier
down_revision: str | None = "c4d8e2f6a1b7"  # pragma: allowlist secret -- migration revision identifier
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    add_retained = not migration.column_exists("flow_version", "retained", conn)
    add_reason = not migration.column_exists("flow_version", "retained_reason", conn)
    if not (add_retained or add_reason):
        return
    # One batch, so SQLite rebuilds the table once.
    with op.batch_alter_table("flow_version") as batch_op:
        if add_retained:
            batch_op.add_column(sa.Column("retained", sa.Boolean(), nullable=False, server_default=sa.false()))
        if add_reason:
            batch_op.add_column(sa.Column("retained_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    columns = [c for c in ("retained_reason", "retained") if migration.column_exists("flow_version", c, conn)]
    if not columns:
        return
    with op.batch_alter_table("flow_version") as batch_op:
        for column in columns:
            batch_op.drop_column(column)
