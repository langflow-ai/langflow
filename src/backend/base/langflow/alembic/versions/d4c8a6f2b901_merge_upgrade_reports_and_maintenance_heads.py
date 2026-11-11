"""Merge the upgrade reports and maintenance migration histories.

Revision ID: d4c8a6f2b901
Revises: 7e2c5a9d1b64, c8f2a4e6b9d1
Create Date: 2026-11-11

Phase: EXPAND

Join the existing histories so databases at either head can upgrade.
"""

from collections.abc import Sequence

revision: str = "d4c8a6f2b901"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("7e2c5a9d1b64", "c8f2a4e6b9d1")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
