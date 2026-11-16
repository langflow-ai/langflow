from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.sql.naming import conv
from sqlmodel import Field, SQLModel

RUN_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
VERSION_SOURCES = ("latest", "history")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Evaluation(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "evaluation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    project_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("folder.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("flow.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    dataset_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("dataset.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    name: str = Field(sa_column=Column(sa.String(255), nullable=False))
    output_vertex_id: str | None = Field(default=None, sa_column=Column(sa.String(255), nullable=True))
    scorers: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    pass_threshold: float = Field(default=0.5, sa_column=Column(sa.Float(), nullable=False, server_default="0.5"))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class EvaluationRun(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "evaluation_run"
    __table_args__ = (
        Index("ix_evaluation_run_evaluation_created", "evaluation_id", "created_at"),
        # One active run per evaluation, enforced by the database so concurrent starts cannot both win.
        Index(
            "uq_evaluation_run_one_active",
            "evaluation_id",
            unique=True,
            sqlite_where=sa.text("status IN ('queued', 'running')"),
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name=conv("ck_evaluation_run_status")
        ),
        CheckConstraint("flow_version_source IN ('latest', 'history')", name=conv("ck_evaluation_run_version_source")),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    evaluation_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("evaluation.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    user_id: UUID = Field(sa_column=Column(sa.Uuid(), nullable=False, index=True))
    job_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    flow_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    flow_name: str = Field(sa_column=Column(sa.String(255), nullable=False))
    flow_version_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("flow_version.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    flow_version_number: int | None = Field(default=None, sa_column=Column(sa.Integer(), nullable=True))
    flow_version_source: str = Field(default="latest", sa_column=Column(sa.String(16), nullable=False))
    dataset_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True, index=True))
    dataset_name: str = Field(sa_column=Column(sa.String(255), nullable=False))
    dataset_revision: int = Field(sa_column=Column(sa.Integer(), nullable=False))
    # Scorers and threshold as they were when the run started, so editing the evaluation never rewrites history.
    config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="queued", sa_column=Column(sa.String(16), nullable=False))
    total_items: int = Field(default=0, sa_column=Column(sa.Integer(), nullable=False, server_default="0"))
    completed_items: int = Field(default=0, sa_column=Column(sa.Integer(), nullable=False, server_default="0"))
    failed_items: int = Field(default=0, sa_column=Column(sa.Integer(), nullable=False, server_default="0"))
    passed_items: int = Field(default=0, sa_column=Column(sa.Integer(), nullable=False, server_default="0"))
    summary: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    estimate: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class EvaluationResult(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "evaluation_result"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_evaluation_result_run_position"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("evaluation_run.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    dataset_item_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    position: int = Field(sa_column=Column(sa.Integer(), nullable=False))
    input: dict = Field(sa_column=Column(JSON, nullable=False))
    expected_output: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    actual_output: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    output_truncated: bool = Field(
        default=False, sa_column=Column(sa.Boolean(), nullable=False, server_default=sa.false())
    )
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    scores: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    passed: bool | None = Field(default=None, sa_column=Column(sa.Boolean(), nullable=True))
    duration_ms: int = Field(default=0, sa_column=Column(sa.Integer(), nullable=False, server_default="0"))
    tokens_flow: int | None = Field(default=None, sa_column=Column(sa.Integer(), nullable=True))
    tokens_judge: int | None = Field(default=None, sa_column=Column(sa.Integer(), nullable=True))
    cost_flow: float | None = Field(default=None, sa_column=Column(sa.Float(), nullable=True))
    cost_judge: float | None = Field(default=None, sa_column=Column(sa.Float(), nullable=True))
    trace_id: str | None = Field(default=None, sa_column=Column(sa.String(64), nullable=True))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
