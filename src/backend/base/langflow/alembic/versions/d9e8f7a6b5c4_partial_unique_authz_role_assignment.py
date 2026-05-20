"""replace authz_role_assignment unique constraint with two partial unique indexes

Revision ID: d9e8f7a6b5c4
Revises: c8e5f4b2a9d7
Create Date: 2026-05-20

Phase: EXPAND

The original ``uq_authz_role_assignment`` UNIQUE(user_id, role_id, domain_type,
domain_id) constraint allowed duplicate global role assignments because SQL
treats NULL ``domain_id`` values as never-equal — two ``("global", NULL)`` rows
for the same (user, role) pair both pass. This migration replaces the broken
constraint with two partial unique indexes:

- ``uq_authz_role_assignment_scoped`` — covers non-global rows (domain_id IS NOT NULL).
- ``uq_authz_role_assignment_global`` — covers the global+NULL case explicitly.

Postgres and SQLite both support partial unique indexes via WHERE clauses.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "d9e8f7a6b5c4"  # pragma: allowlist secret
down_revision: str | None = "c8e5f4b2a9d7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "authz_role_assignment"
_OLD_CONSTRAINT = "uq_authz_role_assignment"
_SCOPED_INDEX = "uq_authz_role_assignment_scoped"
_GLOBAL_INDEX = "uq_authz_role_assignment_global"


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    return index_name in [ix["name"] for ix in inspector.get_indexes(table_name)]


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return

    # Drop the broken constraint if it's still present. Use batch_alter_table so
    # SQLite (which doesn't support ALTER TABLE DROP CONSTRAINT) can recreate
    # the table.
    if migration.constraint_exists(_TABLE, _OLD_CONSTRAINT, conn):
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.drop_constraint(_OLD_CONSTRAINT, type_="unique")

    # Partial unique index for non-global assignments. ``domain_id IS NOT NULL``
    # filters out global rows so they aren't constrained twice.
    if not _index_exists(conn, _TABLE, _SCOPED_INDEX):
        op.create_index(
            _SCOPED_INDEX,
            _TABLE,
            ["user_id", "role_id", "domain_type", "domain_id"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NOT NULL"),
            sqlite_where=sa.text("domain_id IS NOT NULL"),
        )

    # Partial unique index for global assignments — keyed only on
    # (user_id, role_id, domain_type) so NULL domain_id doesn't defeat uniqueness.
    if not _index_exists(conn, _TABLE, _GLOBAL_INDEX):
        op.create_index(
            _GLOBAL_INDEX,
            _TABLE,
            ["user_id", "role_id", "domain_type"],
            unique=True,
            postgresql_where=sa.text("domain_type = 'global' AND domain_id IS NULL"),
            sqlite_where=sa.text("domain_type = 'global' AND domain_id IS NULL"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return

    if _index_exists(conn, _TABLE, _GLOBAL_INDEX):
        op.drop_index(_GLOBAL_INDEX, table_name=_TABLE)
    if _index_exists(conn, _TABLE, _SCOPED_INDEX):
        op.drop_index(_SCOPED_INDEX, table_name=_TABLE)

    # Restore the original (broken) UNIQUE constraint so downgrade returns to
    # the previous schema exactly. Operators downgrading should expect global
    # duplicate behavior to come back.
    if not migration.constraint_exists(_TABLE, _OLD_CONSTRAINT, conn):
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.create_unique_constraint(
                _OLD_CONSTRAINT,
                ["user_id", "role_id", "domain_type", "domain_id"],
            )
