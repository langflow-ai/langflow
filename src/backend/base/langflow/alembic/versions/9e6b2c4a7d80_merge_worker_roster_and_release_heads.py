"""Merge worker roster and release heads.

Revision ID: 9e6b2c4a7d80
Revises: c2e8b4f6a710, 8d4c7a2e9b61
Create Date: 2026-11-08

Phase: EXPAND

Join both published migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "9e6b2c4a7d80"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("c2e8b4f6a710", "8d4c7a2e9b61")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
