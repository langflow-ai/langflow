"""Merge project types and the scaled queue index.

Revision ID: d6a4e8b2c091
Revises: b8e1c47d3f56, f1c5e7a9b3d0
Create Date: 2026-09-16 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

revision: str = "d6a4e8b2c091"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("b8e1c47d3f56", "f1c5e7a9b3d0")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
