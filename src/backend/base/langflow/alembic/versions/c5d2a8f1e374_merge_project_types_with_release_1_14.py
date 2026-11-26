"""Merge project types with the release 1.14 migration head.

Revision ID: c5d2a8f1e374
Revises: e4b7c1d9a203, 7a4c2e9b6d15
Create Date: 2026-11-24 12:00:00.000000

Phase: EXPAND

Both histories remain intact. This merge adds no schema or data operations.
"""

from collections.abc import Sequence

revision: str = "c5d2a8f1e374"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("e4b7c1d9a203", "7a4c2e9b6d15")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
