"""Merge team sharing with the release-1.13.0 integration migrations.

Phase: EXPAND (no DDL - merge point only)

Revision ID: f2a4c6e8b0d1
Revises: b4c7d2e8f1a3, e8a9b0c1d2f3
Create Date: 2026-09-15
"""

from collections.abc import Sequence

revision: str = "f2a4c6e8b0d1"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("b4c7d2e8f1a3", "e8a9b0c1d2f3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the existing migration histories without changing their schemas."""


def downgrade() -> None:
    """Restore both parent markers without removing either branch's schema."""
