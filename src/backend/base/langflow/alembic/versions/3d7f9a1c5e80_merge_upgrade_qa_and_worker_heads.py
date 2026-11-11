"""Merge administrator upgrade QA and worker roster histories.

Revision ID: 3d7f9a1c5e80
Revises: 9b1d3f5a7c8e, f6a2c8e4b901
Create Date: 2026-11-09

Phase: EXPAND

Retain both published histories without changing schema or application data.
"""

from collections.abc import Sequence

revision: str = "3d7f9a1c5e80"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("9b1d3f5a7c8e", "f6a2c8e4b901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
