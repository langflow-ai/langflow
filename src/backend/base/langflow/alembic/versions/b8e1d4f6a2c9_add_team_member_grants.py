"""Add independent provenance sources for effective Team membership.

Phase: EXPAND
Revision ID: b8e1d4f6a2c9
Revises: a3f8b1c9d7e2
Create Date: 2026-08-26

Existing ``authz_team_member`` rows are retained as effective compatibility
state. Exact ``source='manual'`` rows become manual grants; every other source
is preserved as unresolved legacy provenance. No Team or group name is used as
an external identity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b8e1d4f6a2c9"  # pragma: allowlist secret
down_revision: str | None = "a3f8b1c9d7e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "authz_team_member_grant"
_BATCH_SIZE = 1000


def _create_table() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("provider_id", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column("external_group_id", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("legacy_source", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("administrative_actor", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(source_kind = 'manual' AND provider_id IS NULL AND external_group_id IS NULL "
            "AND legacy_source IS NULL) OR "
            "(source_kind = 'directory' AND provider_id IS NOT NULL AND external_group_id IS NOT NULL "
            "AND legacy_source IS NULL) OR "
            "(source_kind = 'legacy' AND provider_id IS NULL AND external_group_id IS NULL "
            "AND legacy_source IS NOT NULL)",
            name="ck_authz_team_member_grant_source",
        ),
        sa.ForeignKeyConstraint(["administrative_actor"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["membership_id"], ["authz_team_member.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_authz_team_member_grant_membership_id",
        TABLE_NAME,
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        "ix_authz_team_member_grant_provider_group",
        TABLE_NAME,
        ["provider_id", "external_group_id"],
        unique=False,
    )
    op.create_index(
        "uq_authz_team_member_grant_manual",
        TABLE_NAME,
        ["membership_id"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'manual'"),
        sqlite_where=sa.text("source_kind = 'manual'"),
    )
    op.create_index(
        "uq_authz_team_member_grant_directory",
        TABLE_NAME,
        ["membership_id", "provider_id", "external_group_id"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'directory'"),
        sqlite_where=sa.text("source_kind = 'directory'"),
    )
    op.create_index(
        "uq_authz_team_member_grant_legacy",
        TABLE_NAME,
        ["membership_id", "legacy_source"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'legacy'"),
        sqlite_where=sa.text("source_kind = 'legacy'"),
    )


def _backfill(conn) -> None:
    metadata = sa.MetaData()
    membership = sa.Table("authz_team_member", metadata, autoload_with=conn)
    grant = sa.Table(TABLE_NAME, metadata, autoload_with=conn)
    last_id = None

    def new_grant_id():
        value = uuid4()
        return value.hex if conn.dialect.name == "sqlite" else value

    while True:
        statement = (
            sa.select(
                membership.c.id,
                membership.c.source,
                membership.c.created_at,
            )
            .outerjoin(grant, grant.c.membership_id == membership.c.id)
            .where(grant.c.id.is_(None))
            .order_by(membership.c.id)
            .limit(_BATCH_SIZE)
        )
        if last_id is not None:
            statement = statement.where(membership.c.id > last_id)
        rows = conn.execute(statement).mappings().all()
        if not rows:
            return
        now = datetime.now(timezone.utc)
        conn.execute(
            grant.insert(),
            [
                {
                    "id": new_grant_id(),
                    "membership_id": row["id"],
                    "source_kind": "manual" if row["source"] == "manual" else "legacy",
                    "provider_id": None,
                    "external_group_id": None,
                    "legacy_source": None if row["source"] == "manual" else (row["source"] or "unresolved")[:512],
                    "administrative_actor": None,
                    "created_at": row["created_at"] or now,
                    "updated_at": row["created_at"] or now,
                }
                for row in rows
            ],
        )
        last_id = rows[-1]["id"]


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("authz_team_member", conn):
        return
    if not migration.table_exists(TABLE_NAME, conn):
        _create_table()
    _backfill(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        op.drop_table(TABLE_NAME)
