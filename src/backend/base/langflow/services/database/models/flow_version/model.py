from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlmodel import JSON, Column, Field, Index, SQLModel, UniqueConstraint

from langflow.schema.data import Data


class FlowVersion(SQLModel, table=True):
    __tablename__ = "flow_version"

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    flow_id: UUID = Field(sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=False))
    flow_data: dict | None = Field(default=None, sa_column=Column(JSON))
    version: int = Field(description="Sequential version number for the flow")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("flow_version_index", "flow_id", "version"),
        UniqueConstraint("flow_id", "version", name="unique_flow_version"),
    )

    def to_data(self):
        serialized = self.model_dump()
        data = {
            "id": serialized.pop("id"),
            "user_id": serialized.pop("user_id"),
            "flow_id": serialized.pop("flow_id"),
            "version": serialized.pop("version"),
            "created_at": serialized.pop("created_at"),
            "flow_data": serialized.pop("flow_data"),
        }
        return Data(data=data)
