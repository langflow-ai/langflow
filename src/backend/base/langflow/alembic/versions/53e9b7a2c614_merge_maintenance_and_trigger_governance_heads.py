"""Merge maintenance and trigger governance migration heads.

Revision ID: 53e9b7a2c614
Revises: a8c2e6f4b9d1, d7e9a1c3f5b8
Create Date: 2026-11-10

Phase: EXPAND

Join the existing histories so databases at either head can upgrade.
"""

from collections.abc import Sequence

revision: str = "53e9b7a2c614"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("a8c2e6f4b9d1", "d7e9a1c3f5b8")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
