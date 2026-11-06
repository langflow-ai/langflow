"""Merge the deployment_copy job type and release 1.14.0 migration heads.

Revision ID: b7e1d4a92c60
Revises: c14fe0b7508c, f2d6b8c4a901
Create Date: 2026-11-04

Phase: EXPAND

Join the deployment_copy job type and the merged 1.13.1 and 1.14.0 heads without changing schema.
"""

from collections.abc import Sequence

revision: str = "b7e1d4a92c60"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("c14fe0b7508c", "f2d6b8c4a901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
