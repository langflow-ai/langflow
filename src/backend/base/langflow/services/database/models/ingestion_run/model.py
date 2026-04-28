"""Persistent record of a single KB ingestion run.

One row per invocation of ``KBIngestionHelper.perform_ingestion``.
Captures the aggregate counters and per-item outcomes produced by a
``KBIngestionSource`` so the Phase 2 visibility UI can drill into a run
without re-walking the vector store.

Design notes:

* ``job_id`` links back to the existing ``job`` table (one-to-one).
  Nullable so component-path ingestions (which don't go through the
  job service today) can still record a run.
* ``source_config`` stores source-specific configuration *minus*
  credentials — cloud connectors in Phase 3 should reference variables
  by name, not embed secret values here.
* ``items`` is a JSON array of per-file outcomes. Chosen over a
  separate ``ingestion_run_item`` table because the typical run size
  (tens to hundreds of files) fits comfortably in a single row, and
  Phase 2's drill-down reads the full list anyway. If future phases
  need sharded per-item queries, we expand (Phase 1+N) by adding a
  dedicated table in a later EXPAND migration.
* ``status`` is a Python-side string so we don't need a second enum
  migration when new outcomes are added; the allow-list is enforced in
  the application layer.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, BigInteger, CheckConstraint, Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres (binary, dedup, GIN-indexable on the ``items``
# column), JSON elsewhere. Matches the variant used in migration
# ``72df732be86b``.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

# Status allow-list — mirrors ``IngestionRunStatus``. Keep in sync
# with migration ``72df732be86b``.
_RUN_STATUS_VALUES = ("pending", "running", "succeeded", "partial", "failed", "cancelled")


class IngestionRunStatus(str, Enum):
    """Run-level outcome visible to the UI.

    Kept distinct from ``JobStatus`` — job status describes scheduling
    (queued/in_progress/completed/etc.), while run status describes the
    ingestion *outcome* (did every file land?).
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"  # some items failed but run completed
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionRunBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID | None = Field(default=None, index=True, nullable=True)
    # ``kb_name`` is the legacy pointer (kept through an
    # expand-contract transition); ``kb_id`` is the new FK.
    kb_name: str = Field(index=True, nullable=False)
    # ``kb_id`` is the FK; ``ON DELETE SET NULL`` is set at the DB
    # layer so KB deletion does not orphan run history — rows remain
    # visible with a null kb_id. The physical FK constraint is
    # created by migration ``e728126476a8``; this ``sa_column`` makes
    # the ORM aware of it so relationships resolve correctly.
    kb_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("knowledge_base.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        ),
    )
    user_id: UUID | None = Field(default=None, index=True, nullable=True)

    source_type: str = Field(index=True, nullable=False)
    source_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JsonVariant, nullable=False),
    )

    status: str = Field(default=IngestionRunStatus.PENDING.value, index=True, nullable=False)
    error_message: str | None = Field(default=None, nullable=True)

    total_items: int = Field(default=0, nullable=False)
    succeeded: int = Field(default=0, nullable=False)
    failed: int = Field(default=0, nullable=False)
    skipped: int = Field(default=0, nullable=False)
    # BigInteger: cumulative byte count of an ingestion run can
    # exceed the int32 ~2GB cap when ingesting large cloud blobs.
    # Matches ``knowledge_base.size_bytes``.
    total_bytes: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )
    chunks_created: int = Field(default=0, nullable=False)

    items: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JsonVariant, nullable=False),
    )

    # User-supplied run-level metadata (tags, categories, custom fields).
    # Persisted here so the run-history UI can render the tags applied to
    # the batch without scanning chunk-level ``source_metadata`` blobs.
    # Per-file overrides are NOT stored here — they live on each chunk's
    # ``source_metadata`` and on the per-item entries in ``items``.
    user_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JsonVariant, nullable=False, server_default="{}"),
    )

    # ``server_default=func.now()`` keeps ``started_at`` populated on
    # raw-SQL inserts. Indexed because list endpoints order by this
    # column — without the index, large run histories sequential-scan.
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class IngestionRun(IngestionRunBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "ingestion_run"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{v}'" for v in _RUN_STATUS_VALUES) + ")",
            name="ck_ingestion_run_status",
        ),
    )
