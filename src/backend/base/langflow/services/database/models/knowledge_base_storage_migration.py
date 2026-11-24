"""Durable, credential-free ledger for local vector-store upgrades."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from langflow.services.database.models.knowledge_base.model import JsonVariant


class KnowledgeBaseStorageMigration(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "knowledge_base_storage_migration"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Retain recovery evidence when explicit retirement removes the routing row.
    kb_id: UUID = Field(sa_column=sa.Column(sa.Uuid(), index=True, nullable=False))
    source_backend: str = Field(default="chroma", nullable=False)
    source_generation: int = Field(nullable=False)
    target_generation: int = Field(nullable=False)
    source_fingerprint: str | None = Field(default=None)
    source_identity: str | None = Field(default=None)
    source_version: str | None = Field(default=None)
    phase: str = Field(default="discovered", nullable=False, index=True)
    attempts: int = Field(default=0, nullable=False)
    error_code: str | None = Field(default=None)
    coordinator: str | None = Field(default=None)
    validation: dict[str, Any] = Field(default_factory=dict, sa_column=sa.Column(JsonVariant, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
