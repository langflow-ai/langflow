"""Fence legacy stores and persist resumable local storage upgrades.

Revision ID: c91d2e3f4a50
Revises: b8e1f3a5c709
Phase: EXPAND. No vector data is read by Alembic.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c91d2e3f4a50"  # pragma: allowlist secret
down_revision = "b8e1f3a5c709"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add storage generations, migration state and the resumable upgrade ledger."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("knowledge_base")}
    with op.batch_alter_table("knowledge_base") as batch:
        if "storage_generation" not in columns:
            batch.add_column(sa.Column("storage_generation", sa.Integer(), nullable=False, server_default="1"))
        if "storage_state" not in columns:
            batch.add_column(sa.Column("storage_state", sa.String(), nullable=False, server_default="ready"))
        if "active_migration_id" not in columns:
            batch.add_column(sa.Column("active_migration_id", sa.Uuid(), nullable=True))
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("knowledge_base")}
    if "ix_knowledge_base_storage_state" not in indexes:
        op.create_index("ix_knowledge_base_storage_state", "knowledge_base", ["storage_state"])
    if "knowledge_base_storage_migration" not in inspector.get_table_names():
        op.create_table(
            "knowledge_base_storage_migration",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("kb_id", sa.Uuid(), sa.ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_backend", sa.String(), nullable=False),
            sa.Column("source_generation", sa.Integer(), nullable=False),
            sa.Column("target_generation", sa.Integer(), nullable=False),
            sa.Column("source_fingerprint", sa.String(), nullable=True),
            sa.Column("source_identity", sa.String(), nullable=True),
            sa.Column("source_version", sa.String(), nullable=True),
            sa.Column("phase", sa.String(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("coordinator", sa.String(), nullable=True),
            sa.Column("validation", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_knowledge_base_storage_migration_kb_id", "knowledge_base_storage_migration", ["kb_id"])
        op.create_index("ix_knowledge_base_storage_migration_phase", "knowledge_base_storage_migration", ["phase"])
    connection.execute(
        sa.text(
            "UPDATE knowledge_base SET storage_state = 'migrating' "
            "WHERE backend_type = 'chroma' AND storage_state = 'ready'"
        )
    )


def downgrade() -> None:
    """Remove the upgrade ledger and storage routing columns."""
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM knowledge_base WHERE backend_type = 'sqlite' LIMIT 1")).first():
        msg = "SQLite knowledge bases require forward repair or the complete pre-upgrade backup"
        raise RuntimeError(msg)
    op.drop_table("knowledge_base_storage_migration")
    with op.batch_alter_table("knowledge_base") as batch:
        batch.drop_index("ix_knowledge_base_storage_state")
        batch.drop_column("active_migration_id")
        batch.drop_column("storage_state")
        batch.drop_column("storage_generation")
