"""Preserve the legacy integration policy storage contract.

Phase: EXPAND

Revision ID: f4b8c1d2e3a6
Revises: 5b3d8f9a2c61
Create Date: 2026-11-05 00:00:00.000000

Empty lists and NULL remain unrestricted, including revisions written by old
replicas after this migration. Deny-all uses a reserved nonempty allowlist that
both old and new replicas enforce, so no data rewrite or schema change is needed.
Keep the revision identifier stable for installations that discovered this head.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f4b8c1d2e3a6"  # pragma: allowlist secret
down_revision: str | None = "5b3d8f9a2c61"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
