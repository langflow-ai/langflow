from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlmodel import Column, DateTime, Field, SQLModel, func

if TYPE_CHECKING:
    from datetime import datetime


class FlowHistoryDeploymentAttachment(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_history_deployment_attachment"

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False))
    history_id: UUID = Field(
        sa_column=Column(ForeignKey("flow_history.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    deployment_id: UUID = Field(
        sa_column=Column(ForeignKey("deployment.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    snapshot_id: str | None = Field(default=None, index=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
