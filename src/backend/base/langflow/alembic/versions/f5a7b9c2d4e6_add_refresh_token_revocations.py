"""Persist refresh token revocations after logout.

Revision ID: f5a7b9c2d4e6
Revises: e4f6a8b2c1d3
Phase: EXPAND
Safe to rollback: YES (revoked tokens become usable until their original expiry)
Services compatible: Older versions ignore the additional table.
"""

import sqlalchemy as sa
from alembic import op

revision = "f5a7b9c2d4e6"  # pragma: allowlist secret - Alembic revision
down_revision = "e4f6a8b2c1d3"  # pragma: allowlist secret - Alembic revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("revoked_refresh_token"):
        return
    op.create_table(
        "revoked_refresh_token",
        sa.Column("token_digest", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_refresh_token_expires_at", "revoked_refresh_token", ["expires_at"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("revoked_refresh_token"):
        op.drop_table("revoked_refresh_token")
