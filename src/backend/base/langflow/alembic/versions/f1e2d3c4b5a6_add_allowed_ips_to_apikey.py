"""Add allowed_ips column to apikey table

Phase: EXPAND

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "f1e2d3c4b5a6"  # pragma: allowlist secret
down_revision: str | None = "d306e5c17c41"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("apikey", conn):
        return
    if not migration.column_exists("apikey", "allowed_ips", conn):
        with op.batch_alter_table("apikey", schema=None) as batch_op:
            batch_op.add_column(sa.Column("allowed_ips", sa.String(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("apikey", conn):
        return
    if not migration.column_exists("apikey", "allowed_ips", conn):
        return
    with op.batch_alter_table("apikey", schema=None) as batch_op:
        batch_op.drop_column("allowed_ips")
