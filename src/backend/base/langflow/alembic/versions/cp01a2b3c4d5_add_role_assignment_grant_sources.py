"""Add independent provenance sources for effective role assignments.

Phase: EXPAND
Revision ID: cp01a2b3c4d5
Revises: b7d5f9a3c2e4
Create Date: 2026-07-30

The table is additive. Downgrade removes provenance but deliberately preserves
all effective ``authz_role_assignment`` rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "cp01a2b3c4d5"  # pragma: allowlist secret
down_revision: str | None = "b7d5f9a3c2e4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "authz_role_assignment_grant"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider_id", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column("external_group", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column("administrative_actor", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(source_kind = 'manual' AND provider_id IS NULL AND external_group IS NULL) "
            "OR (source_kind = 'idp' AND provider_id IS NOT NULL AND external_group IS NOT NULL)",
            name="ck_authz_role_assignment_grant_source",
        ),
        sa.ForeignKeyConstraint(
            ["administrative_actor"],
            ["user.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["authz_role_assignment.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_authz_role_assignment_grant_assignment_id",
        TABLE_NAME,
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        "ix_authz_role_assignment_grant_provider_group",
        TABLE_NAME,
        ["provider_id", "external_group"],
        unique=False,
    )
    op.create_index(
        "uq_authz_role_assignment_grant_manual",
        TABLE_NAME,
        ["assignment_id"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'manual'"),
        sqlite_where=sa.text("source_kind = 'manual'"),
    )
    op.create_index(
        "uq_authz_role_assignment_grant_idp",
        TABLE_NAME,
        ["assignment_id", "provider_id", "external_group"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'idp'"),
        sqlite_where=sa.text("source_kind = 'idp'"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        op.drop_table(TABLE_NAME)
