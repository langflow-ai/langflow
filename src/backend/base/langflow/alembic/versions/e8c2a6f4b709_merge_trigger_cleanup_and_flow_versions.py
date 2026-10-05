"""Merge trigger cleanup and flow-version migration histories.

Revision ID: e8c2a6f4b709
Revises: d7f1b5c9a203, 4e7a2b9c1d05
Create Date: 2026-09-28

Phase: EXPAND
Safe to rollback: YES (this merge has no schema operations)
Services compatible: No schema changes; preserves both existing histories.
"""

from collections.abc import Sequence

revision: str = "e8c2a6f4b709"  # pragma: allowlist secret - Alembic revision
down_revision: str | Sequence[str] | None = ("d7f1b5c9a203", "4e7a2b9c1d05")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
