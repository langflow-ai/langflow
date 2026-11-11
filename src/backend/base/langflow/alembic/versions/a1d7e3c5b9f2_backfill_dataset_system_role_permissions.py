"""Backfill dataset permissions on built-in system roles.

Revision ID: a1d7e3c5b9f2
Revises: 876a81df5a20
Create Date: 2026-10-27

Phase: MIGRATE

Evals datasets are a new authorization resource. Without these slugs a
registered authorization plugin that syncs the built-in roles denies every
non-owner dataset action, including creating a dataset, for viewers and
developers. Mirrors the knowledge-base grants of each role.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a1d7e3c5b9f2"  # pragma: allowlist secret
down_revision: str | None = "876a81df5a20"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_GRANTS: dict[str, tuple[str, ...]] = {
    "viewer": ("dataset:read",),
    "developer": ("dataset:read", "dataset:write", "dataset:create"),
    "admin": ("dataset:read", "dataset:write", "dataset:create", "dataset:delete"),
}


def _authz_role_table():
    return sa.table(
        "authz_role",
        sa.column("name", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("permissions", sa.JSON()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def _permission_list(raw_permissions: Any) -> list[str]:
    if raw_permissions is None:
        return []
    if isinstance(raw_permissions, str):
        raw_permissions = json.loads(raw_permissions)
    return list(raw_permissions)


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("authz_role", conn):
        return

    authz_role = _authz_role_table()
    for role_name, grants in _ROLE_GRANTS.items():
        row = conn.execute(
            sa.select(authz_role.c.permissions)
            .where(authz_role.c.name == role_name)
            .where(authz_role.c.is_system.is_(True))
        ).first()
        if row is None:
            continue
        permissions = _permission_list(row.permissions)
        missing = [grant for grant in grants if grant not in permissions]
        if not missing:
            continue
        conn.execute(
            authz_role.update()
            .where(authz_role.c.name == role_name)
            .where(authz_role.c.is_system.is_(True))
            .values(permissions=[*permissions, *missing], updated_at=datetime.now(timezone.utc))
        )


def downgrade() -> None:
    # Irreversible like the flow:create backfill: after upgrade there is no durable way to tell
    # grants that predated this migration from grants appended by it.
    return
