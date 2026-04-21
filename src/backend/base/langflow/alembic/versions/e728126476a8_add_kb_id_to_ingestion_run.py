"""Add kb_id FK column to ingestion_run

Revision ID: e728126476a8
Revises: 15fe9304bca7
Create Date: 2026-04-20 14:05:00.000000

Phase: EXPAND
Safe to rollback: YES (column is nullable; older services continue
    reading the string ``kb_name`` column they already know about).
Services compatible: All versions. The string ``kb_name`` column stays
    for N-1 compatibility; new code writes both ``kb_name`` and
    ``kb_id``, old code ignores ``kb_id``. A CONTRACT migration to drop
    ``kb_name`` can happen after 30+ days of full adoption — not
    scheduled as part of this phase.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e728126476a8"  # pragma: allowlist secret
down_revision: str | None = "15fe9304bca7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "ingestion_run"
COLUMN_NAME = "kb_id"
INDEX_NAME = "ix_ingestion_run_kb_id"
FK_NAME = "fk_ingestion_run_kb_id_knowledge_base"
REF_TABLE = "knowledge_base"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.Uuid(), nullable=True))

    inspector = sa.inspect(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in existing_indexes:
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.create_index(batch_op.f(INDEX_NAME), [COLUMN_NAME], unique=False)

    # Enforce referential integrity at the DB layer. ``ON DELETE SET NULL``
    # keeps run history readable after a KB is deleted (runs show
    # "deleted KB" rather than disappearing) while guaranteeing no
    # dangling ``kb_id`` values. Only create when the target table
    # exists and the FK isn't already present.
    if migration.table_exists(REF_TABLE, conn) and not migration.foreign_key_exists(TABLE_NAME, FK_NAME, conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.create_foreign_key(
                FK_NAME,
                REF_TABLE,
                [COLUMN_NAME],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    if migration.foreign_key_exists(TABLE_NAME, FK_NAME, conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.drop_constraint(FK_NAME, type_="foreignkey")

    inspector = sa.inspect(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in existing_indexes:
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(INDEX_NAME))

    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.drop_column(COLUMN_NAME)
