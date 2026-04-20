"""Persistent KB identity + configuration.

One row per Knowledge Base. Replaces the long-running
``embedding_metadata.json`` + ``schema.json`` files as the source of
truth — those files stay on disk indefinitely as a fallback (older
service versions read them; a cold-boot backfill upserts rows for any
KB that still lacks one).

Cached statistics (chunk / word / character counts, on-disk size,
file-extension list) live alongside the config so list endpoints can
answer without touching the vector store. The truth remains in
ChromaDB; these columns are refreshed at the end of each ingestion
run via ``KBAnalysisHelper.update_text_metrics``.

Notable columns:

* ``backend_type`` / ``backend_config`` — reserved for Phase 4
  external vector-store backends (MongoDB / Astra / Postgres). Today
  every row is ``"chroma"`` + empty config and nothing reads those
  fields; adding them now keeps Phase 4 code-only.
* ``model_selection`` — the full unified-models dict captured at
  create time. Retrieval + ingestion reconstruct the embedding
  function from this without re-resolving the catalog.
* ``column_config`` — column roles (vectorize / identifier) from the
  tabular ingestion component. JSON array.

Unique constraint on ``(user_id, name)`` because KB directories are
scoped to ``{user}/{kb_name}`` on disk and two same-named KBs under
one user would collide there.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class KnowledgeBaseStatus(str, Enum):
    """Lifecycle state visible to the UI."""

    CREATING = "creating"
    READY = "ready"
    INGESTING = "ingesting"
    FAILED = "failed"


class KnowledgeBaseRecordBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, nullable=False)
    user_id: UUID = Field(index=True, nullable=False)

    embedding_provider: str = Field(nullable=False)
    embedding_model: str = Field(nullable=False)
    model_selection: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    chunk_size: int = Field(default=1000, nullable=False)
    chunk_overlap: int = Field(default=200, nullable=False)
    separator: str | None = Field(default=None, nullable=True)
    column_config: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )

    # Phase 4 surface, reserved today.
    backend_type: str = Field(default="chroma", nullable=False)
    backend_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    # Cached aggregates refreshed after each ingestion run.
    chunks: int = Field(default=0, nullable=False)
    words: int = Field(default=0, nullable=False)
    characters: int = Field(default=0, nullable=False)
    size_bytes: int = Field(default=0, nullable=False)
    source_types: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )

    status: str = Field(default=KnowledgeBaseStatus.READY.value, nullable=False, index=True)
    failure_reason: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class KnowledgeBaseRecord(KnowledgeBaseRecordBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "knowledge_base"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_knowledge_base_user_name"),)
