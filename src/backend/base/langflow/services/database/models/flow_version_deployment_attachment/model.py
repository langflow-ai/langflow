from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import ValidationInfo, field_validator
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import validates
from sqlmodel import Column, DateTime, Field, SQLModel, func

from langflow.services.database.utils import validate_non_empty_string

if TYPE_CHECKING:
    from datetime import datetime


class FlowVersionDeploymentAttachment(SQLModel, table=True):  # type: ignore[call-arg]
    """Tracks which flow versions are attached to which deployments."""

    __tablename__ = "flow_version_deployment_attachment"
    __table_args__ = (UniqueConstraint("flow_version_id", "deployment_id", name="uq_flow_version_deployment"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False))
    flow_version_id: UUID = Field(
        sa_column=Column(ForeignKey("flow_version.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    deployment_id: UUID = Field(
        sa_column=Column(ForeignKey("deployment.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    provider_snapshot_id: str | None = Field(
        ...,
        index=True,
        # DB column is nullable for migration compatibility; app-side writes
        # are validated/normalized at CRUD callsites.
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

    # Primary enforcement is in CRUD helpers (require_non_empty at write boundary).
    # The field_validator is best used for .model_validate calls.
    # The validates decorator is best used for direct ORM object attribute writes.
    @field_validator("provider_snapshot_id")
    @classmethod
    def validate_provider_snapshot_id_field(cls, v: str | None, info: ValidationInfo) -> str:
        if v is None:
            msg = f"{info.field_name} must not be empty"
            raise ValueError(msg)
        return validate_non_empty_string(v, info)

    @validates("provider_snapshot_id")
    def validate_provider_snapshot_id_assignment(self, _key: str, value: str | None) -> str:
        """Safety net for direct ORM writes that bypass CRUD helpers.

        CRUD paths normalize input first to provide deterministic API-layer
        behavior, but this validator still protects ad-hoc model assignment
        and other SQLAlchemy write paths from persisting blank/None values.
        """
        if value is None:
            msg = "provider_snapshot_id must not be empty"
            raise ValueError(msg)
        stripped = value.strip()
        if not stripped:
            msg = "provider_snapshot_id must not be empty"
            raise ValueError(msg)
        return stripped
