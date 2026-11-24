"""Ensure message ingestion records keep their message FK

Phase: EXPAND

Revision ID: b4c2f8e9a1d3
Revises: mb00a1b2c3d4
Create Date: 2026-05-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b4c2f8e9a1d3"  # pragma: allowlist secret
down_revision: str | None = "mb00a1b2c3d4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MIR_TABLE = "message_ingestion_record"
MESSAGE_TABLE = "message"
MESSAGE_FK_NAME = "fk_message_ingestion_record_message_id_message"


def _message_fk_exists(conn) -> bool:
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(MIR_TABLE):
        options = fk.get("options") or {}
        ondelete = (options.get("ondelete") or "").upper()
        if (
            fk.get("constrained_columns") == ["message_id"]
            and fk.get("referred_table") == MESSAGE_TABLE
            and fk.get("referred_columns") == ["id"]
            and ondelete == "CASCADE"
        ):
            return True
    return False


def _constraint_exists(conn, constraint_name: str) -> bool:
    inspector = sa.inspect(conn)
    return any(fk.get("name") == constraint_name for fk in inspector.get_foreign_keys(MIR_TABLE))


def upgrade() -> None:
    conn = op.get_bind()

    # This repairs a PostgreSQL startup race where an older idempotent migration can
    # replay DROP TABLE "message" CASCADE after the memory-base table already exists.
    # That drops only the inbound message_id FK, while the mb00 migration then skips
    # recreating the existing message_ingestion_record table.
    if conn.dialect.name != "postgresql":
        return

    if not migration.table_exists(MIR_TABLE, conn) or not migration.table_exists(MESSAGE_TABLE, conn):
        return

    if _message_fk_exists(conn):
        return

    op.create_foreign_key(
        MESSAGE_FK_NAME,
        MIR_TABLE,
        MESSAGE_TABLE,
        ["message_id"],
        ["id"],
        ondelete="CASCADE",
        postgresql_not_valid=True,
    )


def downgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name != "postgresql" or not migration.table_exists(MIR_TABLE, conn):
        return

    if _constraint_exists(conn, MESSAGE_FK_NAME):
        op.drop_constraint(MESSAGE_FK_NAME, MIR_TABLE, type_="foreignkey")
