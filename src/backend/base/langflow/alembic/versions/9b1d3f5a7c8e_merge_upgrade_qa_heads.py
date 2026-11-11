"""Merge administrator upgrade QA histories.

Revision ID: 9b1d3f5a7c8e
Revises: d8e2f4a6c9b1, a8c2e6f4b9d1
Create Date: 2026-11-09

Phase: EXPAND

Retain both published histories without changing schema or application data.
"""

from collections.abc import Sequence

revision: str = "9b1d3f5a7c8e"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("d8e2f4a6c9b1", "a8c2e6f4b9d1")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
