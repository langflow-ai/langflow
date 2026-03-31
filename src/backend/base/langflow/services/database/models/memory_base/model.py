from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import model_validator
from sqlalchemy import Column, DateTime, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class MemoryBaseBase(SQLModel):
    name: str = Field(index=False)
    flow_id: UUID = Field(index=True)
    user_id: UUID = Field(index=True)
    threshold: int = Field(default=50)
    auto_capture: bool = Field(default=True)
    # Preprocessing config — accepted in payload but logic deferred to future scope
    embedding_model: str = Field(default="")
    preprocessing: bool = Field(default=False)
    preproc_model: str | None = Field(default=None)
    preproc_instructions: str | None = Field(default=None)


class MemoryBase(MemoryBaseBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "memory_base"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # kb_name is auto-generated at creation time — not user-supplied
    kb_name: str = Field(default="")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    sessions: list["MemoryBaseSession"] = Relationship(
        back_populates="memory_base",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class MemoryBaseCreate(MemoryBaseBase):
    user_id: UUID | None = None  # Derived from auth token in the endpoint; not required in request body

    @model_validator(mode="after")
    def preproc_model_required_when_preprocessing(self) -> "MemoryBaseCreate":
        if self.preprocessing and not self.preproc_model:
            msg = "preproc_model is required when preprocessing is enabled"
            raise ValueError(msg)
        return self


class MemoryBaseUpdate(SQLModel):
    name: str | None = None
    threshold: int | None = None
    auto_capture: bool | None = None
    preprocessing: bool | None = None
    preproc_model: str | None = None
    preproc_instructions: str | None = None


class MemoryBaseRead(MemoryBaseBase):
    id: UUID
    kb_name: str
    created_at: datetime


class MemoryBaseSessionBase(SQLModel):
    """Fields shared between the table class and response schemas."""

    session_id: str = Field(index=True)
    cursor_id: UUID | None = Field(default=None)
    total_processed: int = Field(default=0)
    last_sync_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class MemoryBaseSession(MemoryBaseSessionBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "memory_base_session"

    __table_args__ = (
        UniqueConstraint("memory_base_id", "session_id", name="uq_memory_base_session"),
        Index("ix_memory_base_session_lookup", "memory_base_id", "session_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # FK defined via sa_column so Alembic sees the same shape as the migration:
    # inline ForeignKey on the column with ondelete="CASCADE".
    # This matches the pattern used by the File model (ForeignKey on sa_column).
    memory_base_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("memory_base.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    memory_base: MemoryBase = Relationship(back_populates="sessions")


class MemoryBaseSessionRead(MemoryBaseSessionBase):
    id: UUID
    memory_base_id: UUID  # Explicit — not in base to keep base free of DB-layer FK
    pending_count: int = Field(default=0)


class MemoryBaseWorkflowRun(SQLModel, table=True):  # type: ignore[call-arg]
    """Tracks WORKFLOW job runs per (memory_base, session) for threshold-based ingestion.

    One row per WORKFLOW job, per session, per memory base.
    - ``workflow_job_id``: the WORKFLOW job that produced this run (SET NULL on job deletion).
    - ``ingestion_job_id``: set only after the ingestion job that processed this run completes
      successfully. NULL means the run is still pending (not yet counted toward an ingestion).

    Count pending = COUNT(*) WHERE ingestion_job_id IS NULL for a given (memory_base_id, session_id).
    """

    __tablename__ = "memory_base_workflow_run"
    __table_args__ = (
        UniqueConstraint("memory_base_id", "session_id", "workflow_job_id", name="uq_mbwr_mb_session_wf_job"),
        Index("ix_mbwr_mb_session", "memory_base_id", "session_id"),
        Index("ix_mbwr_ingestion_job_id", "ingestion_job_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    memory_base_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("memory_base.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    session_id: str = Field(sa_column=Column(sa.String(), nullable=False))
    workflow_job_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("job.job_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    ingestion_job_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("job.job_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    recorded_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class MessageIngestionRecord(SQLModel, table=True):  # type: ignore[call-arg]
    """M-N join table recording which messages were ingested into which Memory Base by which job.

    One record per (message, session, memory_base) — enforced by the unique constraint.
    Records are written only after a confirmed successful Chroma write (write-on-success).
    On regenerate, all records for the memory_base are deleted atomically alongside the
    cursor reset so that re-ingestion starts clean.
    """

    __tablename__ = "message_ingestion_record"
    __table_args__ = (
        UniqueConstraint("message_id", "session_id", "memory_base_id", name="uq_mir_message_session_mb"),
        Index("ix_mir_message_id", "message_id"),
        Index("ix_mir_job_id", "job_id"),
        Index("ix_mir_memory_base_session", "memory_base_id", "session_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    message_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("message.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    memory_base_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("memory_base.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    job_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("job.job_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # Denormalized from MessageTable.session_id — immutable, avoids JOIN on the hot query path
    session_id: str = Field(sa_column=Column(sa.String(), nullable=False))
    ingested_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
