"""Bound cleanup access-token retention after user deletion.

Revision ID: f9d3b7a5c201
Revises: e8c2a6f4b709
Phase: EXPAND
Safe to rollback: YES (outstanding cleanup falls back to provider expiration)
Services compatible: Older versions ignore the nullable cleanup columns.
"""

import sqlalchemy as sa
from alembic import op

revision = "f9d3b7a5c201"  # pragma: allowlist secret - Alembic revision
down_revision = "e8c2a6f4b709"  # pragma: allowlist secret - Alembic revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("trigger_cleanup")}
    if "encrypted_credential" not in columns:
        op.add_column("trigger_cleanup", sa.Column("encrypted_credential", sa.Text(), nullable=True))
    if "credential_expires_at" not in columns:
        op.add_column("trigger_cleanup", sa.Column("credential_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("trigger_cleanup")}
    with op.batch_alter_table("trigger_cleanup") as batch:
        if "credential_expires_at" in columns:
            batch.drop_column("credential_expires_at")
        if "encrypted_credential" in columns:
            batch.drop_column("encrypted_credential")
