from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlmodel import JSON, Column, Field, Index, SQLModel, UniqueConstraint


class FlowVersion(SQLModel, table=True):
    __tablename__ = "flow_version"

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    version: int = Field(description="Sequential version number for the flow")
    flow_id: UUID = Field(sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=False))
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict | None = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (
        Index("flow_version_index", "flow_id", "version"),
        UniqueConstraint("flow_id", "version", name="unique_flow_version"),
    )
