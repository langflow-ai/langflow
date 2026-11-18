"""Merge upgrade check, maintenance, and release migration heads.

Revision ID: 6b4d1e9c7a25
Revises: 2a4c6e8f0b1d, 53e9b7a2c614, e9c5a1b7d3f6
Create Date: 2026-11-10

Phase: EXPAND

Join the existing histories so databases at any of these revisions can upgrade.
"""

from collections.abc import Sequence

revision: str = "6b4d1e9c7a25"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = (
    "2a4c6e8f0b1d",  # pragma: allowlist secret
    "53e9b7a2c614",  # pragma: allowlist secret
    "e9c5a1b7d3f6",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
