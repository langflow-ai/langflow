"""Backfill flow:create on built-in system roles.

Revision ID: 4f0d2c9a8b7e
Revises: b7c4d8e9f012
Create Date: 2026-06-26

Phase: MIGRATE
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

revision: str = "4f0d2c9a8b7e"  # pragma: allowlist secret
down_revision: str | None = "b7c4d8e9f012"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FLOW_CREATE_PERMISSION = "flow:create"
_ROLE_NAMES = ("developer", "admin")


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


def _set_permissions(conn: sa.Connection, role_name: str, permissions: list[str]) -> None:
    authz_role = _authz_role_table()
    conn.execute(
        authz_role.update()
        .where(authz_role.c.name == role_name)
        .where(authz_role.c.is_system.is_(True))
        .values(
            permissions=permissions,
            updated_at=datetime.now(timezone.utc),
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("authz_role", conn):
        return

    authz_role = _authz_role_table()
    for role_name in _ROLE_NAMES:
        row = conn.execute(
            sa.select(authz_role.c.permissions)
            .where(authz_role.c.name == role_name)
            .where(authz_role.c.is_system.is_(True))
        ).first()
        if row is None:
            continue

        permissions = _permission_list(row.permissions)
        if _FLOW_CREATE_PERMISSION in permissions:
            continue
        _set_permissions(conn, role_name, [*permissions, _FLOW_CREATE_PERMISSION])


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("authz_role", conn):
        return

    authz_role = _authz_role_table()
    for role_name in _ROLE_NAMES:
        row = conn.execute(
            sa.select(authz_role.c.permissions)
            .where(authz_role.c.name == role_name)
            .where(authz_role.c.is_system.is_(True))
        ).first()
        if row is None:
            continue

        permissions = [
            permission for permission in _permission_list(row.permissions) if permission != _FLOW_CREATE_PERMISSION
        ]
        _set_permissions(conn, role_name, permissions)
