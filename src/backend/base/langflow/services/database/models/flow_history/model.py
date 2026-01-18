from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlmodel import JSON, Column, Field, Index, SQLModel

from langflow.schema.data import Data


class FlowHistory(SQLModel, table=True):
    __tablename__ = "flow_history"

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    # must make nullable True for migration compatibility - fix this
    flow_id: UUID = Field(sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=False))
    flow_data: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Index("flow_version_index", "flow_id", "id"),
        Index("flow_id_index", "flow_id"),
    )

    def to_data(self):
        serialized = self.model_dump()
        data = {
            "id": serialized.pop("id"),
            "user_id": serialized.pop("user_id"),
            "flow_id": serialized.pop("flow_id"),
            "flow_data": serialized.pop("flow_data"),
            "created_at": serialized.pop("created_at"),
        }
        return Data(data=data)
