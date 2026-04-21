"""Add knowledge_base table

Revision ID: 15fe9304bca7
Revises: 72df732be86b
Create Date: 2026-04-20 14:00:00.000000

Phase: EXPAND
Safe to rollback: YES (table is new; existing JSON-file KBs continue
    working unchanged because ``kb_helpers`` falls back to disk when a
    DB row is missing).
Services compatible: All versions — older services read KB metadata
    from JSON files and ignore the new table; newer services prefer
    the DB and fall back to JSON.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel.sql.sqltypes import AutoString

# Use JSONB on Postgres (binary, dedup, GIN-indexable) and fall back to
# JSON on SQLite / other dialects. Same type binding used on the
# matching SQLModel so ORM and DDL agree.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

# Allow-list for ``knowledge_base.status``. Keep in sync with
# ``KnowledgeBaseStatus`` (services/database/models/knowledge_base/model.py).
KB_STATUS_VALUES = ("creating", "ready", "ingesting", "failed")

# revision identifiers, used by Alembic.
revision: str = "15fe9304bca7"  # pragma: allowlist secret
down_revision: str | None = "72df732be86b"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "knowledge_base"
UNIQUE_CONSTRAINT_NAME = "uq_knowledge_base_user_name"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    status_values = ", ".join(f"'{v}'" for v in KB_STATUS_VALUES)
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_provider", AutoString(), nullable=False),
        sa.Column("embedding_model", AutoString(), nullable=False),
        sa.Column("model_selection", JsonVariant, nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("separator", AutoString(), nullable=True),
        sa.Column("column_config", JsonVariant, nullable=False),
        sa.Column("backend_type", AutoString(), nullable=False, server_default="chroma"),
        sa.Column("backend_config", JsonVariant, nullable=False),
        sa.Column("chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("source_types", JsonVariant, nullable=False),
        sa.Column("status", AutoString(), nullable=False, server_default="ready"),
        sa.Column("failure_reason", AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_base")),
        sa.UniqueConstraint("user_id", "name", name=UNIQUE_CONSTRAINT_NAME),
        # Referential integrity: a deleted user takes their KBs with
        # them. Application-level scoping already filters by user_id,
        # but DB-enforced CASCADE prevents orphans from surviving a
        # raw ``DELETE FROM user``.
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_knowledge_base_user_id_user", ondelete="CASCADE"),
        # Value allow-list mirrors the ``KnowledgeBaseStatus`` Python
        # enum. A typo in app code now fails at COMMIT instead of
        # silently storing an invalid state.
        sa.CheckConstraint(f"status IN ({status_values})", name="ck_knowledge_base_status"),
    )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_knowledge_base_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_knowledge_base_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_knowledge_base_status"), ["status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_base_status"))
        batch_op.drop_index(batch_op.f("ix_knowledge_base_user_id"))
        batch_op.drop_index(batch_op.f("ix_knowledge_base_name"))

    op.drop_table(TABLE_NAME)
