from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.user.model import User


class DeploymentProviderAccount(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "deployment_provider_account"

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the deployment provider account",
    )
    user_id: UUID = Field(foreign_key="user.id", index=True, description="User owner for this provider account")
    account_id: str | None = Field(default=None, index=True, description="Provider tenant/organization identifier")
    provider_key: str = Field(index=True, description="Deployment adapter routing key")
    backend_url: str = Field(description="Deployment provider backend URL")
    api_key: str = Field(description="Deployment provider API key")
    registered_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="When the user registered the deployment provider account with Langflow.",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        description="When the user last updated the deployment provider account.",
    )

    user: "User" = Relationship(back_populates="deployment_provider_accounts")
    deployments: list["Deployment"] = Relationship(
        back_populates="provider_account",
        sa_relationship_kwargs={"cascade": "delete"},
    )
