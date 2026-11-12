"""Merge maintenance and release migration heads.

Revision ID: a8c2e6f4b9d1
Revises: 4d6e8f0a2b3c, f4b8c1d2e3a6
Create Date: 2026-11-08

Phase: EXPAND

Join both migration histories without changing schema or maintenance state.
"""

from collections.abc import Sequence

revision: str = "a8c2e6f4b9d1"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("4d6e8f0a2b3c", "f4b8c1d2e3a6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
