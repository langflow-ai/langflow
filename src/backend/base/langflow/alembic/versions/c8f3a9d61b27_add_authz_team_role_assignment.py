"""Add the authz_team_role_assignment table.

Phase: EXPAND
Revision ID: c8f3a9d61b27
Revises: b7d5f9a3c2e4
Create Date: 2026-07-28 00:00:00.000000

Team-scoped sibling of ``authz_role_assignment``: binds a team (rather than a
user) to a role at an optional domain, so group-driven role management can be
expressed as "this team holds this role here" and composed with the existing
IdP-group -> team membership sync. Enforcement-side compilers expand rows to
per-member grants; the table itself carries no enforcement semantics, so this
is a pure EXPAND migration with no backfill and no reads from existing tables.

Partial unique indexes mirror ``authz_role_assignment``: a plain
UNIQUE(team_id, role_id, domain_type, domain_id) treats NULL ``domain_id`` as
never-equal, so scoped and unscoped rows are each covered by their own
partial index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c8f3a9d61b27"  # pragma: allowlist secret
down_revision: str | None = "b7d5f9a3c2e4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "authz_team_role_assignment"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("domain_type", sa.String(), nullable=False, server_default="global"),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["team_id"], ["authz_team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["authz_role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
    )
    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_authz_team_role_assignment_team_id"), ["team_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_authz_team_role_assignment_role_id"), ["role_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_authz_team_role_assignment_domain_id"), ["domain_id"], unique=False)
        batch_op.create_index(
            "uq_authz_team_role_assignment_scoped",
            ["team_id", "role_id", "domain_type", "domain_id"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NOT NULL"),
            sqlite_where=sa.text("domain_id IS NOT NULL"),
        )
        batch_op.create_index(
            "uq_authz_team_role_assignment_unscoped",
            ["team_id", "role_id", "domain_type"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NULL"),
            sqlite_where=sa.text("domain_id IS NULL"),
        )
        batch_op.create_index(
            "ix_authz_team_role_assignment_team_domain",
            ["team_id", "domain_type", "domain_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    op.drop_table(TABLE_NAME)
