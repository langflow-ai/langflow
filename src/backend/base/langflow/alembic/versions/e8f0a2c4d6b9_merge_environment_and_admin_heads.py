"""Merge environment-variable and administration migration heads.

Revision ID: e8f0a2c4d6b9
Revises: c9f2e5a7b1d4, d7e9f1a3b5c8
Create Date: 2026-09-08

Phase: EXPAND

Join the release-1.12.1 environment-origin migration with the release-1.13.0
administration migrations so either release line can upgrade to one head.
"""

from collections.abc import Sequence

revision: str = "e8f0a2c4d6b9"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("c9f2e5a7b1d4", "d7e9f1a3b5c8")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both migration histories without changing schema or data."""


def downgrade() -> None:
    """Restore the separate revision heads without changing schema or data."""
