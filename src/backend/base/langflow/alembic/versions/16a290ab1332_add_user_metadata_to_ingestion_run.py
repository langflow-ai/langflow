"""Add user_metadata column to ingestion_run

Revision ID: 16a290ab1332
Revises: e728126476a8
Create Date: 2026-04-28 19:00:00.000000

Phase: EXPAND
Safe to rollback: YES (column is nullable + has a JSON default; older
    services that ignore the column keep round-tripping rows just fine).
Services compatible: All versions. New code writes user-supplied tags
    here; older code ignores the column. Empty objects (``{}``) are
    written when no user metadata is supplied so list endpoints can
    treat presence/absence of tags consistently.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "16a290ab1332"  # pragma: allowlist secret
down_revision: str | None = "e728126476a8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "ingestion_run"
COLUMN_NAME = "user_metadata"

# Mirror the model's JsonVariant choice — JSONB on Postgres, JSON elsewhere.
JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                COLUMN_NAME,
                JsonVariant,
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_column(COLUMN_NAME)
