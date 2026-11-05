"""Add completion receipts for offline root-key database rotation.

Revision ID: c6a81d3e9502
Revises: 1d8d193028c8
Phase: EXPAND
"""

import sqlalchemy as sa
from alembic import op

revision = "c6a81d3e9502"  # pragma: allowlist secret
down_revision = "1d8d193028c8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    from langflow.utils import migration

    if migration.table_exists("secret_rotation", op.get_bind()):
        return
    op.create_table(
        "secret_rotation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("instance_uid", sa.String(128), nullable=True),
        sa.Column("old_fingerprint", sa.String(64), nullable=False),
        sa.Column("new_fingerprint", sa.String(64), nullable=False),
        sa.Column("backup_sha256", sa.String(64), nullable=False),
        sa.Column("rotated_values", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    from langflow.utils import migration

    if migration.table_exists("secret_rotation", op.get_bind()):
        op.drop_table("secret_rotation")
