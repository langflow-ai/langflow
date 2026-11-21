"""Merge maintenance and integration policy release heads.

Phase: EXPAND

Revision ID: e6f8a0b2c4d6
Revises: 4d6e8f0a2b3c, f4b8c1d2e3a6
Create Date: 2026-11-09 00:00:00.000000

This revision joins existing histories without changing data or schema.
"""

from collections.abc import Sequence

revision: str = "e6f8a0b2c4d6"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("4d6e8f0a2b3c", "f4b8c1d2e3a6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
