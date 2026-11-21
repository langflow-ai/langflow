"""Merge scaled background execution and release heads.

Revision ID: 8d4c7a2e9b61
Revises: f1a7c3e95d82, f4b8c1d2e3a6
Create Date: 2026-11-08

Phase: EXPAND

Join both published migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "8d4c7a2e9b61"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("f1a7c3e95d82", "f4b8c1d2e3a6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
