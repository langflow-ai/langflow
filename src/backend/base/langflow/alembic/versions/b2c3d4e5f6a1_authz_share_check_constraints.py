"""add CHECK constraints on authz_share for scope, permission_level, and target consistency

Revision ID: b2c3d4e5f6a1
Revises: f0a1b2c3d4e5
Create Date: 2026-05-20

Phase: EXPAND

Three CHECK constraints on ``authz_share`` to reject ill-formed rows at the
database layer:

* ``ck_authz_share_scope_enum`` — ``scope`` must be one of the documented
  ``ShareScope`` values.
* ``ck_authz_share_permission_enum`` — ``permission_level`` must be one of the
  documented ``SharePermissionLevel`` values.
* ``ck_authz_share_scope_target_consistency`` — TEAM/USER shares require a
  ``target_id``; PRIVATE/PUBLIC shares forbid one. This matches the split
  between ``uq_authz_share_targeted`` and ``uq_authz_share_untargeted``.

Without these the partial unique indexes can be bypassed by inserting a row
whose ``scope`` doesn't match either index's WHERE clause (e.g. a typo'd
``'PRIVATE'``) or whose ``target_id`` is inconsistent with the declared scope.
"""

import contextlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "b2c3d4e5f6a1"  # pragma: allowlist secret
down_revision: str | None = "f0a1b2c3d4e5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "authz_share"
_CONSTRAINTS = (
    ("ck_authz_share_scope_enum", "scope IN ('private', 'team', 'user', 'public')"),
    ("ck_authz_share_permission_enum", "permission_level IN ('read', 'write', 'execute', 'admin')"),
    (
        "ck_authz_share_scope_target_consistency",
        "(scope IN ('team', 'user') AND target_id IS NOT NULL) "
        "OR (scope IN ('private', 'public') AND target_id IS NULL)",
    ),
)


def _check_constraint_exists(conn, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(conn)
    if not hasattr(inspector, "get_check_constraints"):
        return False
    try:
        return constraint_name in [c["name"] for c in inspector.get_check_constraints(table_name)]
    except NotImplementedError:
        # SQLite's inspector reports check constraints via the table SQL text;
        # if the dialect doesn't implement it, treat as "create" (idempotent
        # ALTER will fail loudly on a re-run, but the typical path is fresh).
        return False


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return

    for name, expression in _CONSTRAINTS:
        if _check_constraint_exists(conn, _TABLE, name):
            continue
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.create_check_constraint(name, expression)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return

    for name, _ in reversed(_CONSTRAINTS):
        with op.batch_alter_table(_TABLE, schema=None) as batch_op, contextlib.suppress(Exception):
            batch_op.drop_constraint(name, type_="check")
