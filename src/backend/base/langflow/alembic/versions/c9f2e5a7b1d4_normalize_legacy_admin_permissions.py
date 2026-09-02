"""Normalize legacy administration wildcard permissions.

Phase: MIGRATE
Revision ID: c9f2e5a7b1d4
Revises: b8e1d4f6a2c9
Create Date: 2026-09-01

Older custom roles may store ``user:*``, ``team:*``, or ``role:*``. The
canonical administration vocabulary now uses the equivalent ``manage`` action.
Normalizing stored values keeps those roles editable without accepting new
administration wildcards at the API boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c9f2e5a7b1d4"  # pragma: allowlist secret
down_revision: str | None = "b8e1d4f6a2c9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_ADMINISTRATION_PERMISSIONS = {
    "user:*": "user:manage",
    "team:*": "team:manage",
    "role:*": "role:manage",
}


def _normalize_permissions(permissions: object) -> list[str] | None:
    if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
        return None
    normalized = list(dict.fromkeys(_LEGACY_ADMINISTRATION_PERMISSIONS.get(item, item) for item in permissions))
    return normalized if normalized != permissions else None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("authz_role", conn):
        return
    role = sa.table(
        "authz_role",
        sa.column("id"),
        sa.column("permissions", sa.JSON()),
    )
    rows = conn.execute(sa.select(role.c.id, role.c.permissions)).mappings().all()
    for row in rows:
        normalized = _normalize_permissions(row["permissions"])
        if normalized is not None:
            conn.execute(role.update().where(role.c.id == row["id"]).values(permissions=normalized))


def downgrade() -> None:
    """Keep the semantics-preserving canonical values on downgrade."""
