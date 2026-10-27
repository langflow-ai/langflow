"""Mark triggers an operator paused.

Revision ID: 1d8d193028c8
Revises: e5a7c9b1d3f2
Create Date: 2026-10-15

Phase: EXPAND
Safe to rollback: YES
Services compatible: Versions that do not read trigger.admin_paused_at
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "1d8d193028c8"  # pragma: allowlist secret -- migration revision identifier
down_revision: str | None = "e5a7c9b1d3f2"  # pragma: allowlist secret -- migration revision identifier
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if migration.column_exists("trigger", "admin_paused_at", conn):
        return
    with op.batch_alter_table("trigger") as batch_op:
        batch_op.add_column(sa.Column("admin_paused_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.column_exists("trigger", "admin_paused_at", conn):
        return
    with op.batch_alter_table("trigger") as batch_op:
        batch_op.drop_column("admin_paused_at")
