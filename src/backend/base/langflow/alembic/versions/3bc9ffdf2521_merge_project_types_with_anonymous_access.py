"""Merge project types with the anonymous access migration head.

Revision ID: 3bc9ffdf2521
Revises: c5d2a8f1e374, a09a699afb52
Create Date: 2026-11-26 04:30:00.000000

Phase: EXPAND

Both histories remain intact. This merge adds no schema or data operations.
"""

from collections.abc import Sequence

revision: str = "3bc9ffdf2521"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("c5d2a8f1e374", "a09a699afb52")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
