"""Merge the session version and 1.14.0 migration heads.

Revision ID: 7a4c2e9b6d15
Revises: 9e7a4c2b1d60, a6b8c0d2e4f7
Create Date: 2026-11-17

Phase: EXPAND
"""

from collections.abc import Sequence

revision: str = "7a4c2e9b6d15"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = (
    "9e7a4c2b1d60",  # pragma: allowlist secret
    "a6b8c0d2e4f7",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
