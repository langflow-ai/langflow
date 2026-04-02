import re
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import field_validator
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr
from langflow.services.database.utils import validate_non_empty_string

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User

_MODEL_NAME_RE = re.compile(r"^[a-zA-Z0-9._:/-]+$")
_MODEL_NAME_MAX_LEN = 200


class CustomProvider(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "custom_provider"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_custom_provider_user_name",
        ),
    )

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    name: str = Field()
    base_url: str = Field()
    # MUST be stored encrypted; the CRUD layer encrypts via auth_utils before writing
    # and the Read schema intentionally excludes this field.
    api_key: str = Field()
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: "User" = Relationship(back_populates="custom_providers")
    models: list["CustomProviderModel"] = Relationship(
        back_populates="provider",
        sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"},
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, v: str) -> str:
        if isinstance(v, str):
            return v.rstrip("/")
        return v

    @field_validator("name", "base_url", "api_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)


class CustomProviderModel(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "custom_provider_model"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "name",
            name="uq_custom_provider_model_provider_name",
        ),
    )

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    provider_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(), ForeignKey("custom_provider.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    name: str = Field(max_length=_MODEL_NAME_MAX_LEN)
    tool_calling: bool = Field(default=False)

    provider: "CustomProvider" = Relationship(back_populates="models")

    @field_validator("name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        stripped = v.strip() if isinstance(v, str) else v
        if not stripped:
            msg = "name must not be empty"
            raise ValueError(msg)
        if len(stripped) > _MODEL_NAME_MAX_LEN:
            msg = f"name must not exceed {_MODEL_NAME_MAX_LEN} characters"
            raise ValueError(msg)
        if not _MODEL_NAME_RE.match(stripped):
            msg = "name must only contain letters, digits, and the characters . _ : / -"
            raise ValueError(msg)
        return stripped


# ---------------------------------------------------------------------------
# API Schemas
# ---------------------------------------------------------------------------


class CustomProviderModelSchema(SQLModel):
    """Schema for creating or updating a model within a provider."""

    name: str
    tool_calling: bool = False

    @field_validator("name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        stripped = v.strip() if isinstance(v, str) else v
        if not stripped:
            msg = "model name must not be empty"
            raise ValueError(msg)
        if len(stripped) > _MODEL_NAME_MAX_LEN:
            msg = f"model name must not exceed {_MODEL_NAME_MAX_LEN} characters"
            raise ValueError(msg)
        if not _MODEL_NAME_RE.match(stripped):
            msg = "model name must only contain letters, digits, and the characters . _ : / -"
            raise ValueError(msg)
        return stripped


def _validate_unique_model_names(models: list[CustomProviderModelSchema]) -> list[CustomProviderModelSchema]:
    """Raise ValueError if model names are not unique."""
    seen: set[str] = set()
    for m in models:
        if m.name in seen:
            msg = f"Duplicate model name: {m.name}"
            raise ValueError(msg)
        seen.add(m.name)
    return models


class CustomProviderCreate(SQLModel):
    name: str
    base_url: str
    api_key: str
    models: list[CustomProviderModelSchema] = Field(default_factory=list)

    @field_validator("name", "base_url", "api_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)

    @field_validator("models")
    @classmethod
    def validate_unique_models(cls, v: list[CustomProviderModelSchema]) -> list[CustomProviderModelSchema]:
        return _validate_unique_model_names(v)


class CustomProviderUpdate(SQLModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[CustomProviderModelSchema] | None = None

    @field_validator("name", "base_url", "api_key", mode="before")
    @classmethod
    def validate_non_empty_if_set(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip() if isinstance(v, str) else v
            if not stripped:
                msg = "value must not be empty when provided"
                raise ValueError(msg)
        return v

    @field_validator("models")
    @classmethod
    def validate_unique_models(cls, v: list[CustomProviderModelSchema] | None) -> list[CustomProviderModelSchema] | None:
        if v is not None:
            return _validate_unique_model_names(v)
        return v


class CustomProviderModelRead(SQLModel):
    id: UUID
    provider_id: UUID
    name: str
    tool_calling: bool


class CustomProviderRead(SQLModel):
    """Read schema — api_key intentionally omitted (stored encrypted, never serialized)."""

    id: UUID
    user_id: UUID
    name: str
    base_url: str
    created_at: datetime
    updated_at: datetime
    models: list[CustomProviderModelRead] = Field(default_factory=list)
