"""add SSO identity display details

Revision ID: c6d8e0f2a4b7
Revises: a3f8b1c9d7e2
Create Date: 2026-08-28

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

revision: str = "c6d8e0f2a4b7"  # pragma: allowlist secret
down_revision: str | None = "a3f8b1c9d7e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILE_TABLE = "sso_user_profile"
_IDENTITY_COLUMNS = ("first_name", "last_name", "picture")


def _column_names(conn: sa.Connection) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(_PROFILE_TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_PROFILE_TABLE, conn):
        return

    columns = _column_names(conn)
    with op.batch_alter_table(_PROFILE_TABLE, schema=None) as batch_op:
        for name in _IDENTITY_COLUMNS:
            if name not in columns:
                batch_op.add_column(sa.Column(name, sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_PROFILE_TABLE, conn):
        return

    columns = _column_names(conn)
    with op.batch_alter_table(_PROFILE_TABLE, schema=None) as batch_op:
        for name in reversed(_IDENTITY_COLUMNS):
            if name in columns:
                batch_op.drop_column(name)
