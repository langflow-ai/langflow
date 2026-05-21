"""seed authz system roles — viewer / developer / admin

Revision ID: 8d3a1f9c2e0b
Revises: 7c8d9e0f1a2b
Create Date: 2026-05-21

Phase: EXPAND

Phase 4 of the OSS RBAC rollout. Inserts the three built-in roles referenced
by the design document so an enterprise plugin has a stable bootstrap set
without having to ship its own seed migration. EXPAND because the change is
additive — new rows in an existing table, no schema or data semantics change.

OSS does not interpret these JSON permission lists — they are pure metadata.
The enterprise Casbin plugin reads them during ``PolicySync`` to compile
matching ``p`` rules in ``casbin_rule``.

Idempotent: existing rows with the same ``name`` are left untouched (each
insert is gated by a ``WHERE NOT EXISTS`` subquery against ``name``). Safe to
re-run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "8d3a1f9c2e0b"  # pragma: allowlist secret
down_revision: str | None = "7c8d9e0f1a2b"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Permission templates use ``"{resource}:{action}"`` slugs that map directly
# to Casbin object/action pairs. Enterprise plugins read these to seed
# matching ``p`` rules during ``PolicySync``.
_VIEWER_PERMISSIONS: tuple[str, ...] = (
    "flow:read",
    "flow:execute",
    "deployment:read",
    "project:read",
    "knowledge_base:read",
    "variable:read",
    "file:read",
)

_DEVELOPER_EXTRA: tuple[str, ...] = (
    "flow:write",
    "flow:create",
    "deployment:write",
    "deployment:create",
    "deployment:execute",
    "project:write",
    "project:create",
    "knowledge_base:write",
    "knowledge_base:create",
    "knowledge_base:ingest",
    "variable:write",
    "variable:create",
    "file:write",
    "file:create",
)

_ADMIN_EXTRA: tuple[str, ...] = (
    "flow:delete",
    "flow:deploy",
    "deployment:delete",
    "deployment:deploy",
    "project:delete",
    "knowledge_base:delete",
    "variable:delete",
    "file:delete",
    "share:read",
    "share:create",
    "share:update",
    "share:delete",
)


_SYSTEM_ROLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "viewer",
        "Read-only access to flows, deployments, projects, and supporting resources.",
        _VIEWER_PERMISSIONS,
    ),
    (
        "developer",
        "Author and execute flows; manage variables, knowledge bases, and files.",
        _VIEWER_PERMISSIONS + _DEVELOPER_EXTRA,
    ),
    (
        "admin",
        "Full management of resources and shares within the workspace.",
        _VIEWER_PERMISSIONS + _DEVELOPER_EXTRA + _ADMIN_EXTRA,
    ),
)


def upgrade() -> None:
    conn = op.get_bind()
    authz_role = sa.table(
        "authz_role",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("permissions", sa.JSON()),
        sa.column("parent_role_id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.Uuid()),
    )

    timestamp = datetime.now(timezone.utc)
    for name, description, permissions in _SYSTEM_ROLES:
        already_present = conn.execute(
            sa.select(sa.literal(1)).select_from(authz_role).where(authz_role.c.name == name)
        ).scalar()
        if already_present:
            continue
        # ``sa.Uuid`` adapts ``UUID`` objects per-dialect (CHAR(32) on SQLite,
        # native UUID on Postgres). Passing a bare string skips that path and
        # fails at bind time on SQLite (``'str' object has no attribute
        # 'hex'``), so we pass real UUID objects here.
        # ``sa.JSON`` serializes Python lists natively on both SQLite and
        # Postgres. ``json.dumps`` here would write the JSON-encoded string
        # *inside* the JSON column, which downstream readers (Enterprise
        # PolicySync expects a list) would have to peel a second time.
        conn.execute(
            authz_role.insert().values(
                id=uuid4(),
                name=name,
                description=description,
                is_system=True,
                permissions=list(permissions),
                parent_role_id=None,
                workspace_id=None,
                created_at=timestamp,
                updated_at=timestamp,
                created_by=None,
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    authz_role = sa.table(
        "authz_role",
        sa.column("name", sa.String()),
        sa.column("is_system", sa.Boolean()),
    )
    conn.execute(
        authz_role.delete().where(
            sa.and_(
                authz_role.c.name.in_([name for name, _, _ in _SYSTEM_ROLES]),
                authz_role.c.is_system.is_(True),
            )
        )
    )
