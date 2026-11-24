"""Add user_id and session_id to transaction so a data subject erase can find a person's rows.

Revision ID: a7c2e94d1f36
Revises: 6db8617a3585
Create Date: 2026-10-07

Phase: EXPAND
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "a7c2e94d1f36"  # pragma: allowlist secret
down_revision = "6db8617a3585"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_TABLE = "transaction"
_COLUMNS = (
    ("user_id", sa.Uuid()),
    ("session_id", sa.String()),
)


def _index_exists(name: str, conn) -> bool:
    return any(index["name"] == name for index in sa.inspect(conn).get_indexes(_TABLE))


def upgrade() -> None:
    conn = op.get_bind()
    for name, column_type in _COLUMNS:
        if not migration.column_exists(_TABLE, name, conn):
            op.add_column(_TABLE, sa.Column(name, column_type, nullable=True))
        index = f"ix_{_TABLE}_{name}"
        if not _index_exists(index, conn):
            op.create_index(index, _TABLE, [name], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    for name, _ in reversed(_COLUMNS):
        index = f"ix_{_TABLE}_{name}"
        if _index_exists(index, conn):
            op.drop_index(index, table_name=_TABLE)
        if migration.column_exists(_TABLE, name, conn):
            with op.batch_alter_table(_TABLE) as batch:
                batch.drop_column(name)
