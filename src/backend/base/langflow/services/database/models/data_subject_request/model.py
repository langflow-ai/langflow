"""The ``data_subject_request`` table: one row per GDPR access/erasure request.

The row is both the request queue entry and the durable progress record of its
erasure, so a restart resumes from ``phase``/``cursor``. Subject columns carry
no foreign key: the row must outlive the account it erases.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLModel resolves annotations at runtime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.naming import conv
from sqlmodel import JSON, Column, DateTime, Field, SQLModel, func

from langflow.services.database.models.data_subject_request.schemas import (
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
    DataSubjectType,
)

JsonVariant = JSON().with_variant(JSONB(), "postgresql")


def _values(enum_cls: type) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class DataSubjectRequest(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "data_subject_request"
    __table_args__ = (
        CheckConstraint(f"subject_type IN ({_values(DataSubjectType)})", name=conv("ck_dsr_subject_type")),
        CheckConstraint(f"status IN ({_values(DataSubjectRequestStatus)})", name=conv("ck_dsr_status")),
        CheckConstraint(f"source IN ({_values(DataSubjectRequestSource)})", name=conv("ck_dsr_source")),
        Index("ix_dsr_subject_status", "subject_user_id", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    subject_type: str = Field(sa_column=Column(sa.String(16), nullable=False))
    subject_user_id: UUID = Field(sa_column=Column(sa.Uuid(), nullable=False))
    # Kept only while the request is open: erasing an end user needs the raw id.
    subject_end_user_id: str | None = Field(default=None, sa_column=Column(sa.String(255), nullable=True))
    subject_label: str | None = Field(default=None, sa_column=Column(sa.String(255), nullable=True))
    scope_flow_ids: list[str] | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    source: str = Field(sa_column=Column(sa.String(16), nullable=False))
    requested_by: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    decided_by: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    status: str = Field(
        default=DataSubjectRequestStatus.REQUESTED.value,
        sa_column=Column(sa.String(16), nullable=False, index=True),
    )
    phase: str | None = Field(default=None, sa_column=Column(sa.String(32), nullable=True))
    cursor: dict[str, Any] | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    pending_paths: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    counts: dict[str, Any] | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    error: dict[str, Any] | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    refusal_note: str | None = Field(default=None, sa_column=Column(sa.Text(), nullable=True))
    requested_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    due_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
