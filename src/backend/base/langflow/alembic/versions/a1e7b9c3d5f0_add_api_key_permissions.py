"""Add nullable API key permission policies.

Revision ID: a1e7b9c3d5f0
Revises: 1d8d193028c8
Phase: EXPAND
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "a1e7b9c3d5f0"  # pragma: allowlist secret
down_revision = "1d8d193028c8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not migration.column_exists("apikey", "permissions", op.get_bind()):
        op.add_column("apikey", sa.Column("permissions", sa.JSON(none_as_null=True), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    if not migration.column_exists("apikey", "permissions", connection):
        return
    if connection.execute(sa.text("SELECT 1 FROM apikey WHERE permissions IS NOT NULL LIMIT 1")).first():
        msg = "Revoke restricted API keys before downgrading to a version without scope enforcement"
        raise RuntimeError(msg)
    with op.batch_alter_table("apikey") as batch_op:
        batch_op.drop_column("permissions")
