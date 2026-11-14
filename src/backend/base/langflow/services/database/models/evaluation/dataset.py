from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.sql.naming import conv
from sqlmodel import Field, SQLModel

DATASET_NAME_MAX_LENGTH = 255
DATASET_ITEM_SOURCES = ("manual", "csv", "logs")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "dataset"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_dataset_user_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    name: str = Field(sa_column=Column(sa.String(DATASET_NAME_MAX_LENGTH), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # Bumped on every item change so a run can say "dataset changed since this run".
    revision: int = Field(default=1, sa_column=Column(sa.Integer(), nullable=False, server_default="1"))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DatasetItem(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "dataset_item"
    __table_args__ = (
        Index("ix_dataset_item_dataset_position", "dataset_id", "position"),
        CheckConstraint("source IN ('manual', 'csv', 'logs')", name=conv("ck_dataset_item_source")),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    dataset_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    position: int = Field(sa_column=Column(sa.Integer(), nullable=False))
    input: dict = Field(sa_column=Column(JSON, nullable=False))
    expected_output: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    source: str = Field(default="manual", sa_column=Column(sa.String(16), nullable=False))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
