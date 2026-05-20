"""replace authz_share unique constraint with two partial unique indexes

Revision ID: e4f5a6b7c8d9
Revises: d9e8f7a6b5c4
Create Date: 2026-05-20

Phase: EXPAND

The original ``uq_authz_share_resource_target`` UNIQUE constraint on
(resource_type, resource_id, scope, target_id) did not prevent duplicate
PRIVATE/PUBLIC shares because ``target_id`` is NULL for those scopes and SQL
treats NULL values as never-equal.

Replaces the constraint with two partial unique indexes:

- ``uq_authz_share_targeted`` — covers TEAM/USER scopes (target_id IS NOT NULL).
- ``uq_authz_share_untargeted`` — covers PRIVATE/PUBLIC scopes (target_id IS NULL).

Both Postgres and SQLite support partial unique indexes via WHERE clauses.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "e4f5a6b7c8d9"  # pragma: allowlist secret
down_revision: str | None = "d9e8f7a6b5c4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "authz_share"
_OLD_CONSTRAINT = "uq_authz_share_resource_target"
_TARGETED_INDEX = "uq_authz_share_targeted"
_UNTARGETED_INDEX = "uq_authz_share_untargeted"


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    return index_name in [ix["name"] for ix in inspector.get_indexes(table_name)]


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return

    if migration.constraint_exists(_TABLE, _OLD_CONSTRAINT, conn):
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.drop_constraint(_OLD_CONSTRAINT, type_="unique")

    if not _index_exists(conn, _TABLE, _TARGETED_INDEX):
        op.create_index(
            _TARGETED_INDEX,
            _TABLE,
            ["resource_type", "resource_id", "scope", "target_id"],
            unique=True,
            postgresql_where=sa.text("target_id IS NOT NULL"),
            sqlite_where=sa.text("target_id IS NOT NULL"),
        )

    if not _index_exists(conn, _TABLE, _UNTARGETED_INDEX):
        op.create_index(
            _UNTARGETED_INDEX,
            _TABLE,
            ["resource_type", "resource_id", "scope"],
            unique=True,
            postgresql_where=sa.text("target_id IS NULL"),
            sqlite_where=sa.text("target_id IS NULL"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return

    if _index_exists(conn, _TABLE, _UNTARGETED_INDEX):
        op.drop_index(_UNTARGETED_INDEX, table_name=_TABLE)
    if _index_exists(conn, _TABLE, _TARGETED_INDEX):
        op.drop_index(_TARGETED_INDEX, table_name=_TABLE)

    # Restore the original (broken) UNIQUE constraint so downgrade returns to
    # the previous schema exactly. Operators downgrading should expect
    # duplicate PRIVATE/PUBLIC shares to be possible again.
    if not migration.constraint_exists(_TABLE, _OLD_CONSTRAINT, conn):
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.create_unique_constraint(
                _OLD_CONSTRAINT,
                ["resource_type", "resource_id", "scope", "target_id"],
            )
