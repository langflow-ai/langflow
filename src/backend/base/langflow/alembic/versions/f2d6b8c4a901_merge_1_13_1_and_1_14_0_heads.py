"""Merge the release 1.13.1 and 1.14.0 migration heads.

Revision ID: f2d6b8c4a901
Revises: e4f6a8b2c1d3, c6a81d3e9502
Create Date: 2026-11-03

Phase: EXPAND

Join completed OAuth grants and root-key rotation receipts without changing schema.
"""

from collections.abc import Sequence

revision: str = "f2d6b8c4a901"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("e4f6a8b2c1d3", "c6a81d3e9502")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
