"""Public and internal schemas for persisted integration connections."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from lfx.integrations.capabilities import IntegrationIdentity
from lfx.integrations.models import CONNECTION_NAME_PATTERN, PROVIDER_ID_PATTERN, ConnectionAccount
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictStr, field_validator


class ConnectionOwnershipMode(str, Enum):
    USER = "user"
    INSTANCE = "instance"


class PersistedConnectionStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class ConnectionHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ExecutingIdentityDescriptor(BaseModel):
    """Non-secret identity metadata shown by connection pickers."""

    model_config = ConfigDict(extra="forbid")

    identity: IntegrationIdentity
    account: ConnectionAccount | None = None


class ConnectionCredentialWrite(BaseModel):
    """Write-only credential material encrypted before persistence."""

    model_config = ConfigDict(extra="forbid")

    access_token: SecretStr = Field(min_length=1)
    refresh_token: SecretStr | None = None
    token_type: StrictStr = Field(default="Bearer", min_length=1, max_length=32)
    expires_at: datetime | None = None


class ConnectionCreate(BaseModel):
    """Create metadata plus optional direct-provisioned credential material."""

    model_config = ConfigDict(extra="forbid")

    provider_key: StrictStr = Field(pattern=PROVIDER_ID_PATTERN, max_length=120)
    name: StrictStr = Field(pattern=CONNECTION_NAME_PATTERN, max_length=64)
    display_name: StrictStr = Field(min_length=1, max_length=255)
    ownership_mode: ConnectionOwnershipMode = ConnectionOwnershipMode.USER
    granted_scopes: list[StrictStr] = Field(default_factory=list, max_length=512)
    executing_identity: ExecutingIdentityDescriptor
    allow_non_interactive: bool = False
    credentials: ConnectionCredentialWrite | None = None

    @field_validator("display_name")
    @classmethod
    def _display_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            msg = "display_name must not be blank"
            raise ValueError(msg)
        return value

    @field_validator("granted_scopes")
    @classmethod
    def _scopes_are_unique_and_nonblank(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value]
        if any(not scope for scope in normalized):
            msg = "granted_scopes must not contain blank values"
            raise ValueError(msg)
        if len(set(normalized)) != len(normalized):
            msg = "granted_scopes must not contain duplicates"
            raise ValueError(msg)
        return normalized


class ConnectionRead(BaseModel):
    """Credential-free connection metadata returned by every API route."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID | None
    ownership_mode: ConnectionOwnershipMode
    provider_key: str
    name: str
    display_name: str
    status: PersistedConnectionStatus
    health: ConnectionHealth
    granted_scopes: list[str]
    executing_identity: ExecutingIdentityDescriptor
    allow_non_interactive: bool
    has_credentials: bool
    health_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectionTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_scopes: list[StrictStr] = Field(default_factory=list, max_length=512)

    @field_validator("required_scopes")
    @classmethod
    def _required_scopes_are_unique_and_nonblank(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value]
        if any(not scope for scope in normalized) or len(set(normalized)) != len(normalized):
            msg = "required_scopes must contain unique, non-blank values"
            raise ValueError(msg)
        return normalized
