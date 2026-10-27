"""Add the Evals tables: datasets, their items, evaluations, runs and per-row results.

Revision ID: 876a81df5a20
Revises: 1d8d193028c8
Create Date: 2026-10-26

Phase: EXPAND
Safe to rollback: YES
Services compatible: All; versions without Evals never read these tables

Additive only: five new tables. No existing row is read, rewritten or constrained.
Rolling back drops the datasets and evaluation history and nothing else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "876a81df5a20"  # pragma: allowlist secret
down_revision = "1d8d193028c8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _create_dataset_tables() -> None:
    op.create_table(
        "dataset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_dataset_user_name"),
    )
    op.create_index(op.f("ix_dataset_user_id"), "dataset", ["user_id"])

    op.create_table(
        "dataset_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("source IN ('manual', 'csv', 'logs')", name=op.f("ck_dataset_item_source")),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_item_dataset_id"), "dataset_item", ["dataset_id"])
    op.create_index("ix_dataset_item_dataset_position", "dataset_item", ["dataset_id", "position"])


def _create_evaluation_table() -> None:
    op.create_table(
        "evaluation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("flow_id", sa.Uuid(), nullable=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("output_vertex_id", sa.String(255), nullable=True),
        sa.Column("scorers", sa.JSON(), nullable=False),
        sa.Column("pass_threshold", sa.Float(), server_default="0.5", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["folder.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "project_id", "flow_id", "dataset_id"):
        op.create_index(op.f(f"ix_evaluation_{column}"), "evaluation", [column])


def _create_run_table() -> None:
    op.create_table(
        "evaluation_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("flow_id", sa.Uuid(), nullable=True),
        sa.Column("flow_name", sa.String(255), nullable=False),
        sa.Column("flow_version_id", sa.Uuid(), nullable=True),
        sa.Column("flow_version_number", sa.Integer(), nullable=True),
        sa.Column("flow_version_source", sa.String(16), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("dataset_name", sa.String(255), nullable=False),
        sa.Column("dataset_revision", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("total_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("passed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("estimate", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name=op.f("ck_evaluation_run_status")
        ),
        sa.CheckConstraint(
            "flow_version_source IN ('latest', 'history')", name=op.f("ck_evaluation_run_version_source")
        ),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_run_evaluation_id"), "evaluation_run", ["evaluation_id"])
    op.create_index(op.f("ix_evaluation_run_user_id"), "evaluation_run", ["user_id"])
    op.create_index(op.f("ix_evaluation_run_flow_version_id"), "evaluation_run", ["flow_version_id"])
    op.create_index("ix_evaluation_run_evaluation_created", "evaluation_run", ["evaluation_id", "created_at"])
    op.create_index(op.f("ix_evaluation_run_dataset_id"), "evaluation_run", ["dataset_id"])
    op.create_index(
        "uq_evaluation_run_one_active",
        "evaluation_run",
        ["evaluation_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('queued', 'running')"),
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def _create_result_table() -> None:
    op.create_table(
        "evaluation_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_item_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=True),
        sa.Column("actual_output", sa.Text(), nullable=True),
        sa.Column("output_truncated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_flow", sa.Integer(), nullable=True),
        sa.Column("tokens_judge", sa.Integer(), nullable=True),
        sa.Column("cost_flow", sa.Float(), nullable=True),
        sa.Column("cost_judge", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "position", name="uq_evaluation_result_run_position"),
    )
    op.create_index(op.f("ix_evaluation_result_run_id"), "evaluation_result", ["run_id"])


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("dataset", conn):
        _create_dataset_tables()
    if not migration.table_exists("evaluation", conn):
        _create_evaluation_table()
    if not migration.table_exists("evaluation_run", conn):
        _create_run_table()
    if not migration.table_exists("evaluation_result", conn):
        _create_result_table()


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("evaluation_result", "evaluation_run", "evaluation", "dataset_item", "dataset"):
        if migration.table_exists(table, conn):
            op.drop_table(table)
