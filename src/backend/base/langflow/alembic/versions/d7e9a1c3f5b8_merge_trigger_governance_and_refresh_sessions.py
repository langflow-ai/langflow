"""Merge trigger governance and refresh session heads.

Revision ID: d7e9a1c3f5b8
Revises: c6e8a2f4b901, f5a7b9c2d4e6
Create Date: 2026-11-10

Phase: EXPAND

Join both published migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "d7e9a1c3f5b8"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("c6e8a2f4b901", "f5a7b9c2d4e6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
