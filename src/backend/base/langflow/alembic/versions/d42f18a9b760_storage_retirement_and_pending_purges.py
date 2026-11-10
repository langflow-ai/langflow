"""Retain migration evidence and pending Memory session purges.

Revision ID: d42f18a9b760
Revises: c91d2e3f4a50
Phase: EXPAND
"""

import sqlalchemy as sa
from alembic import op

revision = "d42f18a9b760"  # pragma: allowlist secret
down_revision = "c91d2e3f4a50"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def upgrade() -> None:
    """Preserve retired-store ledgers and queue purges while their stores are fenced."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("memory_base_session")}
    if "purge_pending" not in columns:
        with op.batch_alter_table("memory_base_session") as batch:
            batch.add_column(sa.Column("purge_pending", sa.Boolean(), nullable=False, server_default=sa.false()))
    foreign_keys = inspector.get_foreign_keys("knowledge_base_storage_migration")
    with op.batch_alter_table("knowledge_base_storage_migration", naming_convention=_NAMING) as batch:
        for foreign_key in foreign_keys:
            if foreign_key["constrained_columns"] == ["kb_id"]:
                batch.drop_constraint(
                    foreign_key["name"] or "fk_knowledge_base_storage_migration_kb_id_knowledge_base",
                    type_="foreignkey",
                )


def downgrade() -> None:
    """Refuse to discard pending deletion intents or retained orphaned recovery evidence."""
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM memory_base_session WHERE purge_pending = true LIMIT 1")).first():
        msg = "Complete pending Memory purges before downgrading storage recovery"
        raise RuntimeError(msg)
    if connection.execute(
        sa.text(
            "SELECT 1 FROM knowledge_base_storage_migration m LEFT JOIN knowledge_base k ON k.id = m.kb_id "
            "WHERE k.id IS NULL LIMIT 1"
        )
    ).first():
        msg = "Retained storage ledgers require forward repair or a complete pre-upgrade backup"
        raise RuntimeError(msg)
    with op.batch_alter_table("knowledge_base_storage_migration", naming_convention=_NAMING) as batch:
        batch.create_foreign_key(
            "fk_knowledge_base_storage_migration_kb_id_knowledge_base",
            "knowledge_base",
            ["kb_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("memory_base_session") as batch:
        batch.drop_column("purge_pending")
