"""Track environment-managed variable values.

Revision ID: d7e9f1a3b5c8
Revises: c6d8e0f2a4b7
Create Date: 2026-09-08

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "d7e9f1a3b5c8"  # pragma: allowlist secret
down_revision: str | None = "c6d8e0f2a4b7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Leave existing rows unknown so adoption can compare their decrypted values."""
    conn = op.get_bind()
    if migration.table_exists("variable", conn) and not migration.column_exists(
        "variable", "is_environment_managed", conn
    ):
        with op.batch_alter_table("variable", schema=None) as batch_op:
            batch_op.add_column(sa.Column("is_environment_managed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Remove origin tracking without changing stored variable values."""
    conn = op.get_bind()
    if migration.table_exists("variable", conn) and migration.column_exists("variable", "is_environment_managed", conn):
        with op.batch_alter_table("variable", schema=None) as batch_op:
            batch_op.drop_column("is_environment_managed")
