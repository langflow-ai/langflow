"""add flow audit entry

Revision ID: 6d44d136724d
Revises: 439697865628
Create Date: 2026-09-08 10:12:41.882317

Phase: EXPAND
Safe to rollback: YES (one new table and its indexes; no existing column is read or written).
Services compatible: All versions. Older services never touch the table, and the
    recorder is off unless LANGFLOW_FLOW_AUDIT_ENABLED is set, so an upgrade adds
    an empty table and nothing else.

Records who changed a flow's graph and what they changed. Deliberately not a
version: the row carries a description of the change, never the graph, so it
cannot be restored from and does not grow with the size of the flow.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "6d44d136724d"  # pragma: allowlist secret
down_revision: str | None = "439697865628"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "flow_audit_entry"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(_TABLE, conn):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flow_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("from_version_token", sa.Uuid(), nullable=True),
        sa.Column("to_version_token", sa.Uuid(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_flow_audit_entry_flow_id"), ["flow_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_flow_audit_entry_user_id"), ["user_id"], unique=False)
        batch_op.create_index("ix_flow_audit_entry_flow_updated", ["flow_id", "updated_at"], unique=False)
        batch_op.create_index(
            "ix_flow_audit_entry_flow_user_updated", ["flow_id", "user_id", "updated_at"], unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.drop_index("ix_flow_audit_entry_flow_user_updated")
        batch_op.drop_index("ix_flow_audit_entry_flow_updated")
        batch_op.drop_index(batch_op.f("ix_flow_audit_entry_user_id"))
        batch_op.drop_index(batch_op.f("ix_flow_audit_entry_flow_id"))
    op.drop_table(_TABLE)
