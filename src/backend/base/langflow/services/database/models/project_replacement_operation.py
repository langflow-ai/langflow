"""Durable receipts for atomic project replacement operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, DateTime, String
from sqlmodel import JSON, Field, SQLModel


class ProjectReplacementOperation(SQLModel, table=True):
    """Committed project replacement result keyed by project and operation UUID.

    The project id intentionally has no foreign key: a receipt remains
    queryable after the live project is removed, so clients can resolve a lost
    response without treating a missing project as proof that the operation
    never committed.
    """

    __tablename__ = "project_replacement_operation"

    project_id: UUID = Field(primary_key=True)
    operation_id: UUID = Field(primary_key=True)
    request_digest: str = Field(sa_column=Column(String(64), nullable=False))
    result: dict = Field(sa_column=Column(JSON, nullable=False))
    project_user_id: UUID | None = Field(default=None, nullable=True)
    workspace_id: UUID | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
