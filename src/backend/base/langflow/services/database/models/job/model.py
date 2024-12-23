from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Boolean, Column, DateTime, Field, SQLModel


class Job(SQLModel, table=True):  # type: ignore[call-arg]
    """Model for storing scheduled jobs.

    This model extends APScheduler's job table with additional metadata for Langflow.
    The core APScheduler fields (id, next_run_time, job_state) are used directly by APScheduler,
    while the additional fields are used by Langflow for UI/API purposes.
    """

    # APScheduler required fields
    id: str = Field(max_length=191, primary_key=True)
    next_run_time: datetime | None = Field(sa_column=Column(sa.DateTime(timezone=True)), default=None)
    job_state: bytes | None = Field(sa_column=Column(sa.LargeBinary), default=None)

    # Additional Langflow metadata
    name: str = Field(index=True)
    flow_id: UUID = Field(foreign_key="flow.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, server_default="true", nullable=False))
    created_at: datetime = Field(sa_column=Column(DateTime, server_default=sa.func.now(), nullable=False))
    updated_at: datetime = Field(
        sa_column=Column(DateTime, server_default=sa.func.now(), nullable=False, onupdate=sa.func.now())
    )


class JobRead(SQLModel):
    """Model for reading scheduled jobs."""

    id: str
    job_state: bytes | None
    next_run_time: datetime | None

    name: str
    flow_id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
