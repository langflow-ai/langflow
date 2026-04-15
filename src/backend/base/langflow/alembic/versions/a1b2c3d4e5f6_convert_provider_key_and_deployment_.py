"""convert provider_key and deployment_type to enum columns

Revision ID: a1b2c3d4e5f6
Revises: c0d2ce43b315
Create Date: 2026-03-23 00:00:00.000000

Phase: EXPAND + CONTRACT

Performs a safe column-type conversion from plain String to DB-level
enum for ``provider_key`` (deployment_provider_account) and
``deployment_type`` (deployment).  Each conversion follows the
expand-contract pattern within this migration:

  1. EXPAND   — create the enum type, add a new nullable enum column
  2. MIGRATE  — backfill data from the old string column
  3. CONTRACT — drop old string column, rename new column to original name,
               recreate index

The entire upgrade (and downgrade) is atomic: on PostgreSQL DDL is
transactional; on SQLite ``batch_alter_table`` recreates the table in
one shot.  If any step fails the transaction rolls back with no
partial state.

**Data-compatibility requirement:** every existing value in the string
column must be a valid member of the target enum.  If a row contains a
value not present in the enum (e.g. a provider_key that was never
registered), the backfill will fail — PostgreSQL rejects the
``::enum_name`` cast, and SQLite rejects the CHECK constraint during
table recreation.  The migration is intentionally **not** lenient here:
silently dropping or coercing unknown values would risk data loss.
Before running this migration, verify that all values conform:

  SELECT DISTINCT provider_key FROM deployment_provider_account
    WHERE provider_key NOT IN ('watsonx-orchestrate');

  SELECT DISTINCT deployment_type FROM deployment
    WHERE deployment_type NOT IN ('agent');

Fix or remove non-conforming rows before applying.

Combined into a single atomic migration because these tables are new
and not yet serving production traffic; no N-1 service compatibility
window is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | None = "c0d2ce43b315"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ACCOUNT_TABLE = "deployment_provider_account"
DEPLOYMENT_TABLE = "deployment"

PROVIDER_KEY_ENUM_NAME = "deployment_provider_key_enum"
DEPLOYMENT_TYPE_ENUM_NAME = "deployment_type_enum"

PROVIDER_KEY_VALUES = ("watsonx-orchestrate",)
DEPLOYMENT_TYPE_VALUES = ("agent",)

_IX_PROVIDER_KEY = "ix_deployment_provider_account_provider_key"
_IX_DEPLOYMENT_TYPE = "ix_deployment_deployment_type"


def _backfill_to_enum(conn, table: str, src: str, dst: str, enum_name: str) -> None:
    cast = f"{src}::{enum_name}" if conn.dialect.name == "postgresql" else src
    op.execute(sa.text(f"UPDATE {table} SET {dst} = {cast} WHERE {src} IS NOT NULL AND {dst} IS NULL"))  # noqa: S608


def _backfill_to_string(conn, table: str, src: str, dst: str) -> None:
    cast = f"{src}::text" if conn.dialect.name == "postgresql" else src
    op.execute(sa.text(f"UPDATE {table} SET {dst} = {cast} WHERE {src} IS NOT NULL AND {dst} IS NULL"))  # noqa: S608


def upgrade() -> None:
    conn = op.get_bind()

    provider_key_enum = sa.Enum(*PROVIDER_KEY_VALUES, name=PROVIDER_KEY_ENUM_NAME)
    provider_key_enum.create(conn, checkfirst=True)

    deployment_type_enum = sa.Enum(*DEPLOYMENT_TYPE_VALUES, name=DEPLOYMENT_TYPE_ENUM_NAME)
    deployment_type_enum.create(conn, checkfirst=True)

    # --- provider_key: String -> Enum ---
    if migration.column_exists(PROVIDER_ACCOUNT_TABLE, "provider_key", conn) and not migration.column_exists(
        PROVIDER_ACCOUNT_TABLE, "provider_key_v2", conn
    ):
        # EXPAND
        op.add_column(PROVIDER_ACCOUNT_TABLE, sa.Column("provider_key_v2", provider_key_enum, nullable=True))
        # MIGRATE
        _backfill_to_enum(conn, PROVIDER_ACCOUNT_TABLE, "provider_key", "provider_key_v2", PROVIDER_KEY_ENUM_NAME)
        # CONTRACT — index ops outside batch to avoid SQLite column-lookup
        # race inside _gather_indexes_from_both_tables.
        op.drop_index(_IX_PROVIDER_KEY, table_name=PROVIDER_ACCOUNT_TABLE)
        with op.batch_alter_table(PROVIDER_ACCOUNT_TABLE, schema=None) as batch_op:
            batch_op.drop_column("provider_key")
            batch_op.alter_column("provider_key_v2", new_column_name="provider_key", nullable=False)
        op.create_index(_IX_PROVIDER_KEY, PROVIDER_ACCOUNT_TABLE, ["provider_key"])

    # --- deployment_type: String -> Enum ---
    if migration.column_exists(DEPLOYMENT_TABLE, "deployment_type", conn) and not migration.column_exists(
        DEPLOYMENT_TABLE, "deployment_type_v2", conn
    ):
        # EXPAND
        op.add_column(DEPLOYMENT_TABLE, sa.Column("deployment_type_v2", deployment_type_enum, nullable=True))
        # MIGRATE
        _backfill_to_enum(conn, DEPLOYMENT_TABLE, "deployment_type", "deployment_type_v2", DEPLOYMENT_TYPE_ENUM_NAME)
        # CONTRACT
        op.drop_index(_IX_DEPLOYMENT_TYPE, table_name=DEPLOYMENT_TABLE)
        with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
            batch_op.drop_column("deployment_type")
            batch_op.alter_column("deployment_type_v2", new_column_name="deployment_type", nullable=True)
        op.create_index(_IX_DEPLOYMENT_TYPE, DEPLOYMENT_TABLE, ["deployment_type"])


def downgrade() -> None:
    conn = op.get_bind()

    # --- deployment_type: Enum -> String ---
    if migration.column_exists(DEPLOYMENT_TABLE, "deployment_type", conn) and not migration.column_exists(
        DEPLOYMENT_TABLE, "deployment_type_v2", conn
    ):
        op.add_column(DEPLOYMENT_TABLE, sa.Column("deployment_type_v2", sa.String(), nullable=True))
        _backfill_to_string(conn, DEPLOYMENT_TABLE, "deployment_type", "deployment_type_v2")
        op.drop_index(_IX_DEPLOYMENT_TYPE, table_name=DEPLOYMENT_TABLE)
        with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
            batch_op.drop_column("deployment_type")
            batch_op.alter_column("deployment_type_v2", new_column_name="deployment_type", nullable=True)
        op.create_index(_IX_DEPLOYMENT_TYPE, DEPLOYMENT_TABLE, ["deployment_type"])

    # --- provider_key: Enum -> String ---
    if migration.column_exists(PROVIDER_ACCOUNT_TABLE, "provider_key", conn) and not migration.column_exists(
        PROVIDER_ACCOUNT_TABLE, "provider_key_v2", conn
    ):
        op.add_column(PROVIDER_ACCOUNT_TABLE, sa.Column("provider_key_v2", sa.String(), nullable=True))
        _backfill_to_string(conn, PROVIDER_ACCOUNT_TABLE, "provider_key", "provider_key_v2")
        op.drop_index(_IX_PROVIDER_KEY, table_name=PROVIDER_ACCOUNT_TABLE)
        with op.batch_alter_table(PROVIDER_ACCOUNT_TABLE, schema=None) as batch_op:
            batch_op.drop_column("provider_key")
            batch_op.alter_column("provider_key_v2", new_column_name="provider_key", nullable=False)
        op.create_index(_IX_PROVIDER_KEY, PROVIDER_ACCOUNT_TABLE, ["provider_key"])

    sa.Enum(*DEPLOYMENT_TYPE_VALUES, name=DEPLOYMENT_TYPE_ENUM_NAME).drop(conn, checkfirst=True)
    sa.Enum(*PROVIDER_KEY_VALUES, name=PROVIDER_KEY_ENUM_NAME).drop(conn, checkfirst=True)
