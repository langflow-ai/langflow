"""Add the install-wide model-provider policy store.

Phase: EXPAND
Revision ID: e8f1a2b3c4d5
Revises: cp03a2b3c4d5
Create Date: 2026-07-29 00:00:00.000000

The singleton starts with an empty approved-provider list. Empty deliberately
means unrestricted, preserving existing behavior until an administrator saves
a narrower policy. Its monotonically increasing version lets every worker
notice committed changes without relying on process-local invalidation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e8f1a2b3c4d5"  # pragma: allowlist secret
down_revision: str | None = "cp03a2b3c4d5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "model_provider_policy"
SINGLETON_ID = 1
REQUIRED_COLUMNS = frozenset({"id", "approved_provider_ids", "version"})


def _policy_table() -> sa.TableClause:
    return sa.table(
        TABLE_NAME,
        sa.column("id", sa.Integer()),
        sa.column("approved_provider_ids", sa.JSON()),
        sa.column("version", sa.Integer()),
    )


def _seed_singleton(conn: sa.Connection) -> None:
    table = _policy_table()
    exists = conn.execute(sa.select(table.c.id).where(table.c.id == SINGLETON_ID)).first()
    if exists is None:
        conn.execute(
            table.insert().values(
                id=SINGLETON_ID,
                approved_provider_ids=[],
                version=0,
            )
        )


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        missing_columns = {
            column for column in REQUIRED_COLUMNS if not migration.column_exists(TABLE_NAME, column, conn)
        }
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            msg = f"Existing {TABLE_NAME!r} table is missing required columns: {missing}"
            raise RuntimeError(msg)
        _seed_singleton(conn)
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("approved_provider_ids", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(f"id = {SINGLETON_ID}", name=op.f("ck_model_provider_policy_singleton")),
        sa.CheckConstraint("version >= 0", name=op.f("ck_model_provider_policy_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_provider_policy")),
    )
    _seed_singleton(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    op.drop_table(TABLE_NAME)
