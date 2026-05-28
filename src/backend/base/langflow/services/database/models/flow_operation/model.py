from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
from pydantic import Field as PydanticField
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlmodel import JSON, Field, SQLModel


class FlowOperationActorDelegate(str, Enum):
    SELF = "self"
    AGENT = "agent"


class FlowOperation(SQLModel, table=True):  # type: ignore[call-arg]
    """Durable record of an accepted collaborative operation batch for a flow."""

    __tablename__ = "flow_operation"
    __mapper_args__ = {"confirm_deleted_rows": False}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    protocol_version: int = Field(nullable=False)
    revision: int = Field(sa_column=Column(BigInteger, nullable=False))
    client_id: str = Field(sa_column=Column(String, nullable=False))
    actor_user_id: UUID | None = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    actor_delegate: FlowOperationActorDelegate = Field(
        default=FlowOperationActorDelegate.SELF,
        sa_column=Column(String, nullable=False, server_default=FlowOperationActorDelegate.SELF.value),
    )
    forward_ops: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    backward_ops: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    __table_args__ = (UniqueConstraint("flow_id", "revision", name="unique_flow_operation_revision"),)


class FlowOperationRead(BaseModel):
    """Compact operation row for polling APIs."""

    operation_id: UUID = PydanticField(description="Server-generated operation identity")
    protocol_version: int
    revision: int = PydanticField(ge=0)
    client_id: str
    actor_delegate: FlowOperationActorDelegate
    # Nullable only for historical rows after the actor user has been deleted.
    actor_user_id: UUID | None = None
    forward_ops: list[dict[str, Any]]
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        value = value.replace(microsecond=0)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
