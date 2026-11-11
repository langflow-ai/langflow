"""Merge maintenance and Salesforce migration heads.

Revision ID: c8f2a4e6b9d1
Revises: 53e9b7a2c614, e9c5a1b7d3f6
Create Date: 2026-11-10

Phase: EXPAND

Join both migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "c8f2a4e6b9d1"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("53e9b7a2c614", "e9c5a1b7d3f6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
