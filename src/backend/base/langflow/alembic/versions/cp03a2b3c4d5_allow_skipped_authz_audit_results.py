"""Allow skipped authorization reconciliation audit outcomes.

Phase: EXPAND
Revision ID: cp03a2b3c4d5
Revises: cp02a2b3c4d5
Create Date: 2026-07-31

The wider result vocabulary is backward compatible with existing services.
Downgrade intentionally preserves both the wider constraint and append-only
``skip`` evidence rather than rewriting historical audit rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "cp03a2b3c4d5"  # pragma: allowlist secret
down_revision: str | None = "cp02a2b3c4d5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "authz_audit_log"
_CONSTRAINT_NAME = "ck_authz_audit_log_result_enum"
_RESULT_CHECK = "result IN ('allow', 'deny', 'owner_override', 'skip')"


def upgrade() -> None:
    conn = op.get_bind()
    checks = sa.inspect(conn).get_check_constraints(_TABLE_NAME)
    existing = next((check for check in checks if check["name"] == _CONSTRAINT_NAME), None)
    if existing is not None and "'skip'" in (existing.get("sqltext") or ""):
        return

    with op.batch_alter_table(_TABLE_NAME, schema=None) as batch_op:
        if existing is not None:
            batch_op.drop_constraint(_CONSTRAINT_NAME, type_="check")
        batch_op.create_check_constraint(_CONSTRAINT_NAME, _RESULT_CHECK)


def downgrade() -> None:
    pass
