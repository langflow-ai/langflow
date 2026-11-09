"""Persist native refresh sessions and revocations after logout.

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
    if sa.inspect(op.get_bind()).has_table("refresh_token_session"):
        return
    op.create_table(
        "refresh_token_session",
        sa.Column("session_digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_refresh_token_session_expires_at", "refresh_token_session", ["expires_at"])
    op.create_index("ix_refresh_token_session_user_id", "refresh_token_session", ["user_id"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("refresh_token_session"):
        op.drop_table("refresh_token_session")
