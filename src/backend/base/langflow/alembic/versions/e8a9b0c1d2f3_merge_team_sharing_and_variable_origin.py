"""Merge team-sharing and environment-variable origin heads.

Phase: EXPAND (no DDL - merge point only)

Revision ID: e8a9b0c1d2f3
Revises: bf6c22022777, d7e9f1a3b5c8
Create Date: 2026-09-13
"""

from collections.abc import Sequence

revision: str = "e8a9b0c1d2f3"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("bf6c22022777", "d7e9f1a3b5c8")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both histories after their existing migrations have run."""


def downgrade() -> None:
    """Restore both revision markers without changing either branch's schema."""
