"""Imported reports remain immutable so exports retain their original contents."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class UpgradeReport(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "upgrade_report"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True, server_default=sa.func.now()),
    )
    created_by: UUID | None = Field(default=None, nullable=True)
    generated_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    source_identity: str | None = Field(default=None, max_length=64, index=True)
    target_version: str = Field(max_length=128, index=True)
    flow_count: int
    warning_count: int
    failing_count: int
    content_sha256: str = Field(max_length=64)
    document_json: str = Field(sa_column=sa.Column(sa.Text(), nullable=False))


class UpgradeReportRepair(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "upgrade_report_repair"
    __table_args__ = (sa.Index("ix_upgrade_report_repair_report_time", "report_id", "created_at"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    report_id: UUID = Field(foreign_key="upgrade_report.id", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    created_by: UUID | None = Field(default=None, nullable=True)
    target_sha256: str = Field(max_length=64)
    result_json: str = Field(sa_column=sa.Column(sa.Text(), nullable=False))
