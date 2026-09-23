"""Merge project types and the release UTC storage migration.

Revision ID: e4b7c1d9a203
Revises: b8e1c47d3f56, f2a7c9e4b681
Create Date: 2026-09-23 12:00:00.000000

Phase: EXPAND

Both histories remain intact. This merge adds no schema or data operations.
"""

from collections.abc import Sequence

revision: str = "e4b7c1d9a203"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("b8e1c47d3f56", "f2a7c9e4b681")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
