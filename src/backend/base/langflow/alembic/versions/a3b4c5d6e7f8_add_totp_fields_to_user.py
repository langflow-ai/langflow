"""add totp_secret and totp_enabled columns to user

Revision ID: a3b4c5d6e7f8
Revises: c0d2ce43b315
Create Date: 2026-04-09 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"  # pragma: allowlist secret
down_revision: str | None = "8255e9fc18d9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("user")]

    if "totp_secret" not in columns:
        op.add_column("user", sa.Column("totp_secret", sa.String(), nullable=True))

    if "totp_enabled" not in columns:
        op.add_column("user", sa.Column("totp_enabled", sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("user")]

    if "totp_enabled" in columns:
        op.drop_column("user", "totp_enabled")

    if "totp_secret" in columns:
        op.drop_column("user", "totp_secret")
