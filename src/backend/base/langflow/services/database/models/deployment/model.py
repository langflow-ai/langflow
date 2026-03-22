from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from lfx.services.adapters.deployment.schema import DeploymentType
from pydantic import field_validator
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr
from langflow.services.database.utils import validate_non_empty_string

# NOTE: ``DeploymentType`` is defined and owned by the **lfx** package
# (``lfx.services.adapters.deployment.schema``).  It is imported here as
# a hard dependency because langflow persists deployment metadata on behalf
# of lfx adapters and must guarantee round-trip fidelity of the enum values.
# Existing enum member *values* must never be removed or renamed: the
# ``_DeploymentTypeColumn`` TypeDecorator deserialises stored strings via
# ``DeploymentType(value)`` — if a persisted value no longer maps to a
# member, every read of that row will raise ``ValueError``.
# If lfx ever relocates or splits this enum, this import and any migration
# that references the enum values must be updated in lockstep.


class _DeploymentTypeColumn(sa.TypeDecorator):
    """Stores DeploymentType as a plain string but coerces on read/write."""

    impl = sa.String
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            msg = "deployment_type must not be None"
            raise ValueError(msg)
        if isinstance(value, DeploymentType):
            return value.value
        return DeploymentType(value).value

    def process_result_value(self, value, _dialect):
        return DeploymentType(value)


if TYPE_CHECKING:
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User


class Deployment(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "deployment"
    __table_args__ = (
        UniqueConstraint("deployment_provider_account_id", "name", name="uq_deployment_name_in_provider"),
        UniqueConstraint(
            "deployment_provider_account_id", "resource_key", name="uq_deployment_resource_key_in_provider"
        ),
    )

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    resource_key: str = Field(index=True)
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    # "project" is represented by a Folder row in the existing schema.
    project_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("folder.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    deployment_provider_account_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(), ForeignKey("deployment_provider_account.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    name: str = Field(index=True)
    description: str | None = Field(
        default=None,
        sa_column=Column(sa.Text(), nullable=True),
    )
    # nullable=True at the DB level to satisfy the EXPAND-phase migration
    # validator; the _DeploymentTypeColumn TypeDecorator enforces NOT NULL
    # at the application layer (process_bind_param rejects None).
    deployment_type: DeploymentType = Field(
        sa_column=Column(_DeploymentTypeColumn(), nullable=True, index=True),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: "User" = Relationship(back_populates="deployments")
    deployment_provider_account: "DeploymentProviderAccount" = Relationship(back_populates="deployments")
    folder: "Folder" = Relationship(back_populates="deployments")

    @field_validator("name", "resource_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)


class DeploymentRead(SQLModel):
    id: UUID
    resource_key: str
    user_id: UUID
    project_id: UUID
    deployment_provider_account_id: UUID
    name: str
    description: str | None = None
    deployment_type: DeploymentType
    created_at: datetime
    updated_at: datetime
