"""Merge the upgrade reports and release migration histories.

Revision ID: 7e2c5a9d1b64
Revises: 3d7f9a1c5e80, 6b4d1e9c7a25
Create Date: 2026-11-10

Phase: EXPAND

Join the existing histories so databases at either head can upgrade.
"""

from collections.abc import Sequence

revision: str = "7e2c5a9d1b64"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("3d7f9a1c5e80", "6b4d1e9c7a25")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
