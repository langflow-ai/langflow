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
  create time. Single source of truth for embedding config; the
  ``get_embedding_provider`` / ``get_embedding_model`` helpers in
  ``langflow.api.utils.knowledge_base_service`` read provider / model
  name out of it for display, and retrieval + ingestion reconstruct
  the embedding function from it without re-resolving the catalog.
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

import sqlalchemy as sa
from sqlalchemy import JSON, BigInteger, CheckConstraint, Column, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres for GIN indexability + binary storage; JSON on
# SQLite. The migration uses the identical variant so the ORM and DDL
# produce matching columns.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

# Status allow-list mirrors ``KnowledgeBaseStatus`` below — keep both
# in sync with migration ``15fe9304bca7``.
_KB_STATUS_VALUES = ("creating", "ready", "ingesting", "failed")


class KnowledgeBaseStatus(str, Enum):
    """Lifecycle state visible to the UI."""

    CREATING = "creating"
    READY = "ready"
    INGESTING = "ingesting"
    FAILED = "failed"


class KnowledgeBaseRecordBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, nullable=False)
    # FK with ``ON DELETE CASCADE``: deleting a user deletes their KBs
    # at the DB layer, preventing orphan rows from surviving a raw
    # ``DELETE FROM user``.
    user_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )

    # ``model_selection`` is the canonical source of truth for embedding
    # config. The legacy flat columns (``embedding_provider`` /
    # ``embedding_model``) were removed in favor of the
    # ``get_embedding_provider`` / ``get_embedding_model`` helpers in
    # ``langflow.api.utils.knowledge_base_service`` that read from this
    # dict. The API response shape still surfaces the flat fields as a
    # convenience view (derived via those helpers in
    # ``record_to_metadata_dict``).
    model_selection: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JsonVariant, nullable=False),
    )

    chunk_size: int = Field(default=1000, nullable=False)
    chunk_overlap: int = Field(default=200, nullable=False)
    separator: str | None = Field(default=None, nullable=True)
    column_config: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JsonVariant, nullable=False),
    )

    # Phase 4 surface, reserved today.
    backend_type: str = Field(default="chroma", nullable=False)
    backend_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JsonVariant, nullable=False),
    )

    # Cached aggregates refreshed after each ingestion run.
    chunks: int = Field(default=0, nullable=False)
    words: int = Field(default=0, nullable=False)
    characters: int = Field(default=0, nullable=False)
    size_bytes: int = Field(
        default=0,
        # BigInteger matches the migration: a cloud-backed KB with
        # millions of chunks can blow past int32's ~2GB cap.
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )
    source_types: list[str] = Field(
        default_factory=list,
        sa_column=Column(JsonVariant, nullable=False),
    )

    status: str = Field(default=KnowledgeBaseStatus.READY.value, nullable=False, index=True)
    failure_reason: str | None = Field(default=None, nullable=True)

    # ``server_default=func.now()`` keeps the column populated even
    # when rows are inserted via raw SQL (backfill, admin scripts).
    # The Python ``default_factory`` remains so ORM-level inserts get
    # a timezone-aware UTC value without a round-trip.
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


class KnowledgeBaseRecord(KnowledgeBaseRecordBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "knowledge_base"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_knowledge_base_user_name"),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{v}'" for v in _KB_STATUS_VALUES) + ")",
            name="ck_knowledge_base_status",
        ),
    )
