"""Merge the trigger ledger and release 1.13.0 migration heads.

Revision ID: e6f9a2b4c8d1
Revises: c5a8e2f7d9b1, 1d28fd31a982
Create Date: 2026-09-16

Phase: EXPAND

Join both existing histories without changing their revisions or the schema.
"""

from collections.abc import Sequence

revision: str = "e6f9a2b4c8d1"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("c5a8e2f7d9b1", "1d28fd31a982")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
