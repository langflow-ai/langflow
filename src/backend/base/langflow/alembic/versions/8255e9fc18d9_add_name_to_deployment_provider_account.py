"""add name to deployment_provider_account

Revision ID: 8255e9fc18d9
Revises: a1b2c3d4e5f6
Create Date: 2026-03-24 19:23:55.194564

Phase: EXPAND

Adds a ``name`` column (non-nullable) to ``deployment_provider_account``
and a composite unique constraint on ``(provider_key, name)`` so that
names are unique within a given provider.

Existing rows are backfilled with ``'account-<first-8-chars-of-id>'``
before the unique constraint is applied.

Risks
-----
* **Backfill collision (extremely unlikely):** The backfill derives names
  from the first 8 hex characters of each row's UUID.  A collision can
  only occur between two rows that share the same ``provider_key`` *and*
  whose UUIDs share the same first 8 hex chars (~1-in-4-billion per
  pair).  If this ever triggers an ``IntegrityError`` during migration,
  re-run after manually assigning distinct names to the affected rows.

* **NOT-NULL on existing data:** The column is added as nullable, then
  backfilled, then altered to non-nullable.  If a concurrent transaction
  inserts a row without a ``name`` between the ADD COLUMN and the ALTER
  COLUMN steps, the ALTER will fail.  This is mitigated by running
  migrations during a maintenance window or with exclusive table locks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "8255e9fc18d9"  # pragma: allowlist secret
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
    # Uses the SQL-standard ``||`` operator (via SQLAlchemy's .concat())
    # and ``substr()``, both of which work on PostgreSQL and SQLite.
    # The unique constraint is on (provider_key, name), so collisions can
    # only happen between rows sharing the same provider_key whose UUID
    # hex representations share the same first 8 characters
    # which is unlikely given the deployments feature is not officially shipped.
    table = sa.table(
        TABLE_NAME,
        sa.column("id", sa.Uuid()),
        sa.column(COLUMN_NAME, AutoString()),
    )

    op.execute(
        table.update()
        .where(table.c.name.is_(None))
        .values(name=sa.literal("account-").concat(sa.func.substr(sa.cast(table.c.id, sa.String), 1, 8)))
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
