"""Merge the transaction attribution and audit events heads.

``release-1.13.0`` advanced to ``f3a9c1d7b025`` while the transaction
attribution columns were being written on top of the earlier head, so two heads
exist once the branches meet. Join the parents without rewriting either
published history, so database startup can resolve ``head`` again.

Revision ID: b4e8d2f1c9a3
Revises: a7c2e94d1f36, f3a9c1d7b025
Create Date: 2026-10-07

Phase: EXPAND
Safe to rollback: YES (no schema or data changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b4e8d2f1c9a3"  # pragma: allowlist secret
down_revision: tuple[str, str] = (
    "a7c2e94d1f36",  # pragma: allowlist secret
    "f3a9c1d7b025",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the migration heads without changing schema or data."""


def downgrade() -> None:
    """Restore the parent heads without reverting their schema changes."""
