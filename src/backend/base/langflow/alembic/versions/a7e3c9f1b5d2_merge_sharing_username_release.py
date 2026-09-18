"""Merge team sharing with the release username-uniqueness migration.

Phase: EXPAND (no DDL - merge point only)

Revision ID: a7e3c9f1b5d2
Revises: f2a4c6e8b0d1, 1d28fd31a982
Create Date: 2026-09-18
"""

from collections.abc import Sequence

revision: str = "a7e3c9f1b5d2"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("f2a4c6e8b0d1", "1d28fd31a982")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the published histories without changing their schemas or data."""


def downgrade() -> None:
    """Restore both parent markers without removing either branch's schema."""
