from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, SQLModel


class FlowRun(SQLModel, table=True):
    __tablename__ = "flow_run"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(index=True)
    status: str = Field(default="pending", index=True)
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None, sa_column=Column(sa.Text()))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(sa.DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(sa.DateTime(timezone=True), nullable=False)
    )
