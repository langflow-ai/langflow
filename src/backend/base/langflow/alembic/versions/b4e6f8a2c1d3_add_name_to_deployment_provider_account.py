"""add name column to deployment_provider_account

Revision ID: b4e6f8a2c1d3
Revises: a1b2c3d4e5f6
Create Date: 2026-03-24 00:00:00.000000

Phase: EXPAND

Adds a ``name`` column (non-nullable) to ``deployment_provider_account``
and a composite unique constraint on ``(provider_key, name)`` so that
names are unique within a given provider.

Existing rows are backfilled with ``'account-<first-8-chars-of-id>'``
before the unique constraint is applied.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "b4e6f8a2c1d3"  # pragma: allowlist secret
down_revision: str | None = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "deployment_provider_account"
COLUMN_NAME = "name"
UNIQUE_CONSTRAINT_NAME = "uq_deployment_provider_account_provider_name"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN_NAME, AutoString(), nullable=True))

    # Backfill existing rows with a unique name derived from the row id.
    # The unique constraint is on (provider_key, name), so collisions can
    # only happen between rows sharing the same provider_key whose UUID
    # hex representations share the same first 8 characters -- a ~1-in-4-
    # billion chance per pair, which is safe for any realistic dataset.
    table = sa.table(
        TABLE_NAME,
        sa.column("id", sa.Uuid()),
        sa.column(COLUMN_NAME, AutoString()),
    )
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.execute(
            table.update()
            .where(table.c.name.is_(None))
            .values(name=sa.func.concat("account-", sa.func.left(sa.cast(table.c.id, sa.String), 8)))
        )
    else:
        op.execute(
            table.update()
            .where(table.c.name.is_(None))
            .values(name=sa.func.concat("account-", sa.func.substr(sa.cast(table.c.id, sa.String), 1, 8)))
        )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.alter_column(COLUMN_NAME, nullable=False)
        batch_op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, ["provider_key", COLUMN_NAME])


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_constraint(UNIQUE_CONSTRAINT_NAME, type_="unique")
        batch_op.drop_column(COLUMN_NAME)
