from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import field_validator
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr
from langflow.services.database.utils import (
    normalize_string_or_none,
    validate_non_empty_string,
    validate_non_empty_string_optional,
)

if TYPE_CHECKING:
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.user.model import User


class DeploymentProviderAccount(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "deployment_provider_account"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider_url",
            "provider_tenant_id",
            name="uq_deployment_provider_account_user_url_tenant",
        ),
    )

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    # provider_tenant_id participates in a unique constraint. When NULL,
    # SQL-standard databases (PostgreSQL, SQLite) treat NULL != NULL in unique
    # constraints, so multiple rows with the same (user_id, provider_url) are
    # allowed when provider_tenant_id is NULL.  This is intentional: a provider
    # may not require a tenant/organization identifier.
    provider_tenant_id: str | None = Field(default=None, index=True)
    provider_key: str = Field(index=True)
    provider_url: str = Field()
    # MUST be stored encrypted; the CRUD layer encrypts via auth_utils before writing
    # and the Read schema MUST intentionally excludes this field.
    api_key: str = Field()
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: "User" = Relationship(back_populates="deployment_provider_accounts")
    deployments: list["Deployment"] = Relationship(
        back_populates="deployment_provider_account",
        sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"},
    )

    @field_validator("provider_tenant_id", mode="before")
    @classmethod
    def normalize_tenant_id(cls, v: str | None) -> str | None:
        return normalize_string_or_none(v)

    @field_validator("provider_key", "provider_url", "api_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)


class DeploymentProviderAccountCreate(SQLModel):
    provider_tenant_id: str | None = None
    provider_key: str
    provider_url: str
    api_key: str

    @field_validator("provider_tenant_id", mode="before")
    @classmethod
    def normalize_tenant_id(cls, v: str | None) -> str | None:
        return normalize_string_or_none(v)

    @field_validator("provider_key", "provider_url", "api_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)


class DeploymentProviderAccountRead(SQLModel):
    id: UUID
    user_id: UUID
    provider_tenant_id: str | None = None
    provider_key: str
    provider_url: str
    created_at: datetime
    updated_at: datetime
    # api_key intentionally omitted -- stored encrypted, never serialize credentials to API responses


class DeploymentProviderAccountUpdate(SQLModel):
    # All fields default to None.  API routes consuming this schema must check
    # ``model_fields_set`` to distinguish "field omitted" (keep existing value)
    # from "field explicitly set to null" (clear the value).  The CRUD layer's
    # ``update_provider_account`` uses an ``_UNSET`` sentinel for the same
    # purpose on ``provider_tenant_id``.
    provider_tenant_id: str | None = None
    provider_key: str | None = None
    provider_url: str | None = None
    api_key: str | None = None

    @field_validator("provider_tenant_id", mode="before")
    @classmethod
    def normalize_tenant_id(cls, v: str | None) -> str | None:
        return normalize_string_or_none(v)

    @field_validator("provider_key", "provider_url", "api_key", mode="before")
    @classmethod
    def validate_non_empty_if_provided(cls, v: str | None, info: object) -> str | None:
        return validate_non_empty_string_optional(v, info)
