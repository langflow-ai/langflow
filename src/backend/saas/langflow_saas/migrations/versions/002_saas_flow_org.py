"""Add saas_flow_org shadow table for org-scoped flow ownership.

Revision ID: 002saas
Revises: 001saas
Create Date: 2026-04-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as _sa_inspect

revision: str = "002saas"
down_revision: str | None = "001saas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_uuid = sa.Uuid()


def _has_table(name: str) -> bool:
    return _sa_inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("saas_flow_org"):
        return

    op.create_table(
        "saas_flow_org",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column("flow_id", _uuid, nullable=False, unique=True),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by",
            _uuid,
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_flow_org_flow", "saas_flow_org", ["flow_id"], unique=True)
    op.create_index("ix_saas_flow_org_org", "saas_flow_org", ["org_id"])


def downgrade() -> None:
    op.drop_table("saas_flow_org")
