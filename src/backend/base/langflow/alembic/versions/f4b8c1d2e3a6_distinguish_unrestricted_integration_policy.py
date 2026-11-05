"""Distinguish unrestricted integration policy from deny-all.

Phase: MIGRATE

Revision ID: f4b8c1d2e3a6
Revises: 5b3d8f9a2c61
Create Date: 2026-11-05 00:00:00.000000

Existing empty approved-integration lists meant unrestricted. Convert them to
NULL so an explicit empty list can represent deny-all going forward.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f4b8c1d2e3a6"  # pragma: allowlist secret
down_revision: str | None = "5b3d8f9a2c61"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_TABLE = "policy_bundle_revision"
COLUMN_NAME = "approved_integration_provider_ids"


def _table() -> sa.Table:
    return sa.table(
        REVISION_TABLE,
        sa.column("revision", sa.Integer()),
        sa.column(COLUMN_NAME, sa.JSON()),
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(REVISION_TABLE, conn) or not migration.column_exists(
        REVISION_TABLE, COLUMN_NAME, conn
    ):
        return

    table = _table()
    rows = conn.execute(sa.select(table.c.revision, table.c.approved_integration_provider_ids)).mappings()
    for row in rows:
        if row[COLUMN_NAME] == []:
            conn.execute(
                table.update()
                .where(table.c.revision == row["revision"])
                .values(approved_integration_provider_ids=sa.null())
            )

    with op.batch_alter_table(REVISION_TABLE) as batch_op:
        batch_op.alter_column(
            COLUMN_NAME,
            existing_type=sa.JSON(),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(REVISION_TABLE, conn) or not migration.column_exists(
        REVISION_TABLE, COLUMN_NAME, conn
    ):
        return

    table = _table()
    rows = conn.execute(sa.select(table.c.revision, table.c.approved_integration_provider_ids)).mappings()
    for row in rows:
        if row[COLUMN_NAME] is None:
            conn.execute(
                table.update().where(table.c.revision == row["revision"]).values(approved_integration_provider_ids=[])
            )
    with op.batch_alter_table(REVISION_TABLE) as batch_op:
        batch_op.alter_column(
            COLUMN_NAME,
            existing_type=sa.JSON(),
            nullable=True,
            server_default=sa.text("'[]'"),
        )
