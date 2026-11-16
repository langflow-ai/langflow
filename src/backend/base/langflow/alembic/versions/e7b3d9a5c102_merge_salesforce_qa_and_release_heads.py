"""Merge Salesforce QA and release migration histories.

Revision ID: e7b3d9a5c102
Revises: f6a2c8e4b901, f6b9d2e4a731
Create Date: 2026-11-09

Phase: EXPAND

Preserve both published merge revisions without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "e7b3d9a5c102"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("f6a2c8e4b901", "f6b9d2e4a731")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
