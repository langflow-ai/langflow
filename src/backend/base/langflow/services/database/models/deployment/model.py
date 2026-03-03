from __future__ import annotations

from datetime import datetime  # noqa: TC003 - needed at runtime for SQLModel fields and Pydantic schemas
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.services.database.utils import validate_non_empty_string

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
    user_id: UUID = Field(foreign_key="user.id", index=True)
    # "project" is represented by a Folder row in the existing schema.
    project_id: UUID = Field(foreign_key="folder.id", index=True)
    # CASCADE behaviour is enforced at the migration/DDL level.
    deployment_provider_account_id: UUID = Field(foreign_key="deployment_provider_account.id", index=True)
    name: str = Field(index=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: User = Relationship(back_populates="deployments")
    deployment_provider_account: DeploymentProviderAccount = Relationship(back_populates="deployments")
    folder: Folder = Relationship(back_populates="deployments")

    @field_validator("name", "resource_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)


class DeploymentCreate(SQLModel):
    resource_key: str
    deployment_provider_account_id: UUID
    project_id: UUID
    name: str

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
    created_at: datetime
    updated_at: datetime
