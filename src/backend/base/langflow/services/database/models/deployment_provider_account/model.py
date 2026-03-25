from datetime import datetime
from typing import TYPE_CHECKING, Self
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import field_validator, model_validator
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.deployment_provider_account.utils import (
    validate_provider_url,
    validate_tenant_url_consistency,
)
from langflow.services.database.utils import (
    normalize_string_or_none,
    validate_non_empty_string,
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
        UniqueConstraint(
            "provider_key",
            "name",
            name="uq_deployment_provider_account_provider_name",
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
    # The DB-level ``deployment_provider_key_enum`` constraint is defined
    # by a Langflow alembic migration.  The enum is Langflow-owned (see
    # ``DeploymentProviderKey`` above); LFX uses plain strings for adapter
    # registry keys and does not reference this enum.
    #
    # To add a new value to ``deployment_provider_key_enum``:
    #   1. Add the member to ``DeploymentProviderKey`` in this module.
    #   2. Register the corresponding adapter in LFX and mapper in Langflow.
    #   3. Create a Langflow alembic migration that runs:
    #        op.execute(
    #            "ALTER TYPE deployment_provider_key_enum ADD VALUE '<new>'"
    #        )
    #      For SQLite (dev/test) this is a no-op; the CHECK constraint is
    #      recreated automatically by ``batch_alter_table``.
    #   4. Deploy the migration before any code writes the new value.
    #
    # Removing or renaming a value is **strongly discouraged**.  Existing
    # rows reference the old string; renaming silently breaks every read
    # of those rows and invalidates any provider accounts using that key.
    # If absolutely necessary:
    #   1. Create a migration that (a) updates existing rows to the
    #      replacement value, then (b) recreates the enum type without
    #      the old value (PostgreSQL requires CREATE TYPE … / ALTER COLUMN
    #      … TYPE … USING …; SQLite uses ``batch_alter_table``).
    #   2. Update or remove the member in ``DeploymentProviderKey``.
    #   3. Update the adapter registry key and mapper registration to
    #      match the new value.
    provider_key: DeploymentProviderKey = Field(
        sa_column=Column(
            SQLEnum(
                DeploymentProviderKey,
                name="deployment_provider_key_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            index=True,
        ),
    )
    name: str = Field(description="User-chosen display name, unique within a provider_key (e.g. 'staging', 'prod').")
    provider_url: str = Field(description="Provider service URL used for deployment crud in the account.")
    # MUST be stored encrypted; the CRUD layer encrypts via auth_utils before writing
    # and the Read schema intentionally excludes this field.
    api_key: str = Field(description="Provider credential material. Stored encrypted; never returned in API responses.")
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

    @field_validator("name", "api_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)

    @field_validator("provider_url")
    @classmethod
    def validate_url(cls, v: str, info: object) -> str:
        return validate_provider_url(v, info)

    @model_validator(mode="after")
    def validate_tenant_consistency(self) -> Self:
        validate_tenant_url_consistency(self.provider_url, self.provider_tenant_id, self.provider_key)
        return self


class DeploymentProviderAccountRead(SQLModel):
    id: UUID
    user_id: UUID
    name: str
    provider_tenant_id: str | None = None
    provider_key: DeploymentProviderKey
    provider_url: str
    created_at: datetime
    updated_at: datetime
    # api_key intentionally omitted -- stored encrypted, never serialize credentials to API responses
