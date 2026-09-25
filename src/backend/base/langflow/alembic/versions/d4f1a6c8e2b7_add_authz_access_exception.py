"""Add authz_access_exception for per-resource role-access revocation.

Phase: EXPAND
Revision ID: d4f1a6c8e2b7
Revises: f2a7c9e4b681
Create Date: 2026-09-15

A new, empty table — no backfill needed. One row means "this user's
role/scope-derived access to this resource is revoked"; it is deliberately
independent of ``authz_share`` (an explicit share on the same resource is
untouched by a row here).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d4f1a6c8e2b7"  # pragma: allowlist secret
down_revision: str | None = "f2a7c9e4b681"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "authz_access_exception"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "resource_type",
            "resource_id",
            name="uq_authz_access_exception_target",
        ),
    )
    op.create_index(
        "ix_authz_access_exception_user_id",
        TABLE_NAME,
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_authz_access_exception_resource_type",
        TABLE_NAME,
        ["resource_type"],
        unique=False,
    )
    op.create_index(
        "ix_authz_access_exception_resource_id",
        TABLE_NAME,
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_authz_access_exception_resource",
        TABLE_NAME,
        ["resource_type", "resource_id"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        op.drop_table(TABLE_NAME)
