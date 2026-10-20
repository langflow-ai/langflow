"""Merge background job metrics and personal default project migrations.

Both migrations extend f2a7c9e4b681 independently. Keep both upgrade paths valid
for databases that have already applied either branch.

Revision ID: c7e9b2d4f6a8
Revises: b3f7c2a91d48, d8f2c3a4b5e6
Create Date: 2026-09-27

Phase: EXPAND
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c7e9b2d4f6a8"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("b3f7c2a91d48", "d8f2c3a4b5e6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two additive migration branches without changing schema or data."""


def downgrade() -> None:
    """Restore the two parent heads without reverting either parent's schema."""
