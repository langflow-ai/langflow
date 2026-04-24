"""add api_key_source to deployment_provider_account

Revision ID: 7f8e9d0c1b2a
Revises: 2a5defa5ddc0
Create Date: 2026-04-24 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "7f8e9d0c1b2a"  # pragma: allowlist secret
down_revision: str | None = "2a5defa5ddc0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "deployment_provider_account"
COLUMN_NAME = "api_key_source"
DEFAULT_VALUE = "raw"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN_NAME, sa.String(), nullable=True, server_default=DEFAULT_VALUE))

    table = sa.table(TABLE_NAME, sa.column(COLUMN_NAME, sa.String()))
    op.execute(table.update().where(table.c.api_key_source.is_(None)).values(api_key_source=DEFAULT_VALUE))

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.alter_column(COLUMN_NAME, nullable=False, server_default=DEFAULT_VALUE)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_column(COLUMN_NAME)
