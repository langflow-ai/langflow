from __future__ import annotations

from datetime import datetime  # noqa: TC003 - needed at runtime for Pydantic schemas
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.user.model import User


class DeploymentProviderAccount(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "deployment_provider_account"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider_url",
            "account_id",
            name="uq_deployment_provider_account_user_url_account",
        ),
    )

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    # account_id participates in a unique constraint. When NULL, most databases
    # treat NULL != NULL, so multiple rows with the same (user_id, provider_url)
    # are allowed when account_id is NULL. This is intentional: a provider may
    # not require a tenant/organization identifier.
    account_id: str | None = Field(default=None, index=True)
    provider_key: str = Field(index=True)
    provider_url: str = Field()
    api_key: str = Field()
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: User = Relationship(back_populates="deployment_provider_accounts")
    deployments: list[Deployment] = Relationship(
        back_populates="provider_account",
        sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"},
    )

    @field_validator("provider_key", "provider_url")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            msg = "Field must not be empty"
            raise ValueError(msg)
        return stripped


class DeploymentProviderAccountCreate(SQLModel):
    account_id: str | None = None
    provider_key: str
    provider_url: str
    api_key: str


class DeploymentProviderAccountRead(SQLModel):
    id: UUID
    user_id: UUID
    account_id: str | None = None
    provider_key: str
    provider_url: str
    created_at: datetime
    updated_at: datetime
    # api_key intentionally omitted -- never serialize credentials


class DeploymentProviderAccountUpdate(SQLModel):
    account_id: str | None = None
    provider_key: str | None = None
    provider_url: str | None = None
    api_key: str | None = None
