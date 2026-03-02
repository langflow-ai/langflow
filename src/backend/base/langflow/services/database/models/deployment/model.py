from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from datetime import datetime

    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.user.model import User


class Deployment(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "deployment"
    __table_args__ = (UniqueConstraint("provider_account_id", "name", name="uq_deployment_name_in_provider"),)

    id: UUID | None = Field(default_factory=uuid4, primary_key=True, description="Unique ID for the deployment")
    resource_key: str = Field(index=True, description="ID assigned by Langflow or the deployment provider")
    user_id: UUID = Field(foreign_key="user.id", index=True, description="User owner for this deployment")
    project_id: UUID = Field(foreign_key="folder.id", index=True, description="Project this deployment belongs to")
    provider_account_id: UUID = Field(
        foreign_key="deployment_provider_account.id",
        index=True,
        description="Deployment provider account used by this deployment",
    )
    name: str = Field(index=True, description="User-defined deployment name unique within a provider account")
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="When the deployment was created.",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        description="When the deployment was last updated.",
    )

    user: User = Relationship(back_populates="deployments")
    provider_account: DeploymentProviderAccount = Relationship(back_populates="deployments")
