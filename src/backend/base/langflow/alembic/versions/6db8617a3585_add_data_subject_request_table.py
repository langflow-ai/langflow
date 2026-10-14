"""Add the data_subject_request table for GDPR access and erasure requests.

Revision ID: 6db8617a3585
Revises: b8e1f3a5c709
Create Date: 2026-09-30

Phase: EXPAND
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy.dialects.postgresql import JSONB

JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")

revision = "6db8617a3585"  # pragma: allowlist secret
down_revision = "b8e1f3a5c709"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_TABLE = "data_subject_request"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(_TABLE, conn):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("subject_end_user_id", sa.String(255), nullable=True),
        sa.Column("subject_label", sa.String(255), nullable=True),
        sa.Column("scope_flow_ids", JsonVariant, nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(32), nullable=True),
        sa.Column("cursor", JsonVariant, nullable=True),
        sa.Column("pending_paths", JsonVariant, nullable=True),
        sa.Column("counts", JsonVariant, nullable=True),
        sa.Column("error", JsonVariant, nullable=True),
        sa.Column("refusal_note", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("subject_type IN ('builder', 'end_user')", name=op.f("ck_dsr_subject_type")),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'erasing', 'done', 'refused', 'withdrawn')",
            name=op.f("ck_dsr_status"),
        ),
        sa.CheckConstraint("source IN ('self', 'admin', 'api')", name=op.f("ck_dsr_source")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_subject_request")),
    )
    op.create_index(op.f("ix_data_subject_request_status"), _TABLE, ["status"], unique=False)
    op.create_index("ix_dsr_subject_status", _TABLE, ["subject_user_id", "status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_TABLE, conn):
        return
    op.drop_index("ix_dsr_subject_status", table_name=_TABLE)
    op.drop_index(op.f("ix_data_subject_request_status"), table_name=_TABLE)
    op.drop_table(_TABLE)
