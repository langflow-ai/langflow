"""Merge the Evals and upgrade-report migration histories.

Revision ID: 310c015b3c92
Revises: d7e9f1a3b5c7, 9c4b7e2a6d10
Create Date: 2026-11-11

Phase: EXPAND

Join both histories without changing schema or existing evaluation data.
"""

from collections.abc import Sequence

revision: str = "310c015b3c92"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("d7e9f1a3b5c7", "9c4b7e2a6d10")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
