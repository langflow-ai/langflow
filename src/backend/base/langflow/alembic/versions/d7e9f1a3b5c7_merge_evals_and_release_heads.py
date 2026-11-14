"""Merge the Evals and release migration histories.

Revision ID: d7e9f1a3b5c7
Revises: a1d7e3c5b9f2, f2d6b8c4a901
Create Date: 2026-11-04

Phase: EXPAND

Join both histories without changing schema or existing evaluation data.
"""

from collections.abc import Sequence

revision: str = "d7e9f1a3b5c7"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("a1d7e3c5b9f2", "f2d6b8c4a901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
