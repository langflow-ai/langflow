"""Merge represented audit identity and release trigger heads.

Revision ID: c8f3e6a2b901
Revises: a6f81c2d903b, 1d8d193028c8
Create Date: 2026-10-20

Phase: EXPAND

Preserve upgrade paths from both the audit branch and release-1.14.0.
"""

from collections.abc import Sequence

revision: str = "c8f3e6a2b901"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("a6f81c2d903b", "1d8d193028c8")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both predecessor branches without changing their schemas."""


def downgrade() -> None:
    """Keep the merge point compatible with both predecessor branches."""
