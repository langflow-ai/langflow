from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, SQLModel, func

if TYPE_CHECKING:
    from datetime import datetime


class FlowVersionDeploymentAttachment(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_version_deployment_attachment"
    __table_args__ = (UniqueConstraint("flow_version_id", "deployment_id", name="uq_flow_version_deployment"),)

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False))
    flow_version_id: UUID = Field(
        sa_column=Column(ForeignKey("flow_version.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    deployment_id: UUID = Field(
        sa_column=Column(ForeignKey("deployment.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    provider_snapshot_id: str | None = Field(
        default=None,
        index=True,
        description=(
            "Opaque provider-assigned identifier for the materialized snapshot "
            "(e.g. a wxO tool ID, a K8s ConfigMap name, an S3 key). "
            "Links this Langflow flow version to its provider-side resource."
        ),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
