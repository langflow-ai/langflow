"""Merge background execution and skipped trigger event histories.

Revision ID: f6b9d2e4a731
Revises: 8d4c7a2e9b61, a8e4c2f6b901
Create Date: 2026-11-09

Phase: EXPAND

Join both published migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "f6b9d2e4a731"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("8d4c7a2e9b61", "a8e4c2f6b901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
