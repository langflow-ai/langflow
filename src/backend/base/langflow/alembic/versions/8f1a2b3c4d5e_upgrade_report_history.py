"""Store imported upgrade report history.

Phase: EXPAND
Revision ID: 8f1a2b3c4d5e
Revises: 4d6e8f0a2b3c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f1a2b3c4d5e"  # pragma: allowlist secret
down_revision: str | None = "4d6e8f0a2b3c"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("upgrade_report"):
        op.create_table(
            "upgrade_report",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("source_identity", sa.String(64), nullable=True),
            sa.Column("target_version", sa.String(128), nullable=False),
            sa.Column("flow_count", sa.Integer(), nullable=False),
            sa.Column("warning_count", sa.Integer(), nullable=False),
            sa.Column("failing_count", sa.Integer(), nullable=False),
            sa.Column("content_sha256", sa.String(64), nullable=False),
            sa.Column("document_json", sa.Text(), nullable=False),
        )
        op.create_index("ix_upgrade_report_created_at", "upgrade_report", ["created_at"])
        op.create_index("ix_upgrade_report_source_identity", "upgrade_report", ["source_identity"])
        op.create_index("ix_upgrade_report_target_version", "upgrade_report", ["target_version"])
    if not sa.inspect(op.get_bind()).has_table("upgrade_report_repair"):
        op.create_table(
            "upgrade_report_repair",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("report_id", sa.Uuid(), sa.ForeignKey("upgrade_report.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("target_sha256", sa.String(64), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=False),
        )
        op.create_index("ix_upgrade_report_repair_report_time", "upgrade_report_repair", ["report_id", "created_at"])


def downgrade() -> None:
    op.drop_table("upgrade_report_repair")
    op.drop_table("upgrade_report")
