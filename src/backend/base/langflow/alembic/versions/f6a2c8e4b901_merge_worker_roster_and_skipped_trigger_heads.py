"""Merge worker roster and skipped trigger event heads.

Revision ID: f6a2c8e4b901
Revises: 9e6b2c4a7d80, a8e4c2f6b901
Create Date: 2026-11-09

Phase: EXPAND

Join both published migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "f6a2c8e4b901"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("9e6b2c4a7d80", "a8e4c2f6b901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
