"""add audit log

Revision ID: 8f2a41c07b93
Revises: 690d24733555
Create Date: 2026-09-09 10:31:02.114530

Phase: EXPAND
Safe to rollback: YES (one new table and its indexes; nothing else reads it).
Services compatible: All versions. Older services never write or read the table,
    and the feature is gated by ``LANGFLOW_AUDIT_ENABLED`` (off by default), so an
    in-flight client cannot break across the upgrade.

``event`` and ``resource_type`` are plain strings rather than a SQLAlchemy Enum
on purpose: an Enum makes adding an event name a migration on both backends —
PostgreSQL needs ``ALTER TYPE ... ADD VALUE`` and SQLite needs a table rebuild
whenever the new value is the longest — while the vocabulary is meant to grow.

``created_at`` carries a server-side default so every replica stamps rows from
the database's clock instead of its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "8f2a41c07b93"  # pragma: allowlist secret
down_revision: str | None = "690d24733555"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "audit_log"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE, conn):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("event", sa.String(), nullable=False),
        # No foreign key to ``user``: attribution has to survive deleting the user.
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_resource", TABLE, ["resource_type", "resource_id", "created_at"], unique=False)
    op.create_index("ix_audit_log_user", TABLE, ["user_id", "created_at"], unique=False)
    op.create_index("ix_audit_log_event", TABLE, ["event", "created_at"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE, conn):
        return

    op.drop_index("ix_audit_log_event", table_name=TABLE)
    op.drop_index("ix_audit_log_user", table_name=TABLE)
    op.drop_index("ix_audit_log_resource", table_name=TABLE)
    op.drop_table(TABLE)
