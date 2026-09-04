"""add user_id to message table

Phase: EXPAND

Adds a nullable, indexed ``user_id`` column to the ``message`` table so chat-history
retrieval can be scoped to the owning user. This closes cross-user chat-history
disclosure on the authenticated run path, where an attacker who reuses a victim's
``session_id`` could otherwise read the victim's messages (CWE-200). The column is
nullable so existing rows are unaffected; retrieval only filters on it when a user
scope is supplied.

Revision ID: 9b3e7c1f0a52
Revises: 4f0d2c9a8b7e
Create Date: 2026-06-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils.migration import column_exists

revision: str = "9b3e7c1f0a52"  # pragma: allowlist secret
down_revision: str | None = "4f0d2c9a8b7e"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not column_exists("message", "user_id", conn):
        with op.batch_alter_table("message", schema=None) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
            batch_op.create_index("ix_message_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if column_exists("message", "user_id", conn):
        with op.batch_alter_table("message", schema=None) as batch_op:
            batch_op.drop_index("ix_message_user_id")
            batch_op.drop_column("user_id")
