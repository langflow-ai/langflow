"""add expires_at to api_key table

Revision ID: f6b3ce6845d4
Revises: mb01b2c3d4e5
Create Date: 2026-05-25 16:30:52.248882

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "f6b3ce6845d4"  # pragma: allowlist secret
down_revision: str | None = "mb01b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "apikey"
COLUMN_NAME = "expires_at"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return
    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN_NAME, sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return
    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_column(COLUMN_NAME)
