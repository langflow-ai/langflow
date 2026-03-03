from __future__ import annotations

from datetime import datetime  # noqa: TC003 - needed at runtime for Pydantic schemas
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

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
    project_id: UUID = Field(foreign_key="folder.id", index=True)
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
    folder: Folder | None = Relationship(back_populates="deployments")

    @field_validator("name", "resource_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        stripped = v.strip()
        if not stripped:
            field = getattr(info, "field_name", "Field")
            msg = f"{field} must not be empty"
            raise ValueError(msg)
        return stripped


class DeploymentRead(SQLModel):
    id: UUID
    resource_key: str
    user_id: UUID
    project_id: UUID
    deployment_provider_account_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
