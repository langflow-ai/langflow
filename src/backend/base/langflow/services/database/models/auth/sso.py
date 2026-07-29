"""SSO plugin tables.

These tables are used by the SSO plugin for identity and provider configuration.
Migrations are managed by Langflow (OSS); the plugin must not create or
migrate these tables.

Plugins must use these tables via the models exported from
``langflow.services.database.models`` (e.g. ``SSOUserProfile``, ``SSOConfig``).
"""

import re
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypeAlias
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, TypeAdapter, model_validator
from pydantic import Field as PydanticField
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index
from sqlalchemy.orm import validates
from sqlmodel import Field, SQLModel
from typing_extensions import Self

from langflow.schema.serialize import UUIDstr
from langflow.services.database.models.auth.sso_secret import is_sso_client_secret_envelope

_SSO_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _generate_sso_slug() -> str:
    """Generate an opaque, URL-safe connection identifier."""
    return f"sso-{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OIDCProviderSettings(BaseModel):
    """OIDC-specific settings stored in ``sso_config.provider_settings``."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["oidc"] = "oidc"
    discovery_url: str | None = None
    redirect_uri: str | None = None
    scopes: str | None = "openid email profile"
    token_endpoint: str | None = None
    authorization_endpoint: str | None = None
    jwks_uri: str | None = None
    issuer: str | None = None
    client_id: str | None = None


# Add future protocol variants to this discriminated union. The database schema
# remains unchanged because every variant is stored in the same JSON column.
SSOProviderSettings: TypeAlias = Annotated[OIDCProviderSettings, PydanticField(discriminator="protocol")]
_PROVIDER_SETTINGS_ADAPTER = TypeAdapter(SSOProviderSettings)


def _validate_provider_settings(protocol: str, value: object) -> SSOProviderSettings:
    settings = _PROVIDER_SETTINGS_ADAPTER.validate_python(value)
    if settings.protocol != protocol:
        msg = f"provider_settings protocol {settings.protocol!r} does not match sso_config.protocol {protocol!r}"
        raise ValueError(msg)
    return settings


class _ProviderSettingsJSON(sa.TypeDecorator):
    """Persist validated provider settings as JSON and restore their Pydantic type."""

    impl = sa.JSON
    cache_ok = True

    def process_bind_param(
        self,
        value: SSOProviderSettings | dict[str, Any] | None,
        _dialect: sa.engine.Dialect,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        settings = _PROVIDER_SETTINGS_ADAPTER.validate_python(value)
        return _PROVIDER_SETTINGS_ADAPTER.dump_python(settings, mode="json")

    def process_result_value(
        self,
        value: dict[str, Any] | None,
        _dialect: sa.engine.Dialect,
    ) -> SSOProviderSettings | None:
        if value is None:
            return None
        return _PROVIDER_SETTINGS_ADAPTER.validate_python(value)


class SSOUserProfile(SQLModel, table=True):  # type: ignore[call-arg]
    """SSO profile per user.

    ``sso_provider`` stores the immutable ``SSOConfig.slug`` as a documented-soft
    reference; no database foreign key is intentionally enforced.
    """

    __tablename__ = "sso_user_profile"
    # Use Index(unique=True) to match migrations (create_index); avoids model/DB mismatch.
    __table_args__ = (
        Index("uq_sso_user_profile_provider_user", "sso_provider", "sso_user_id", unique=True),
        Index("uq_sso_user_profile_user_provider", "user_id", "sso_provider", unique=True),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    sso_provider: str = Field(description="Immutable SSOConfig.slug connection identifier")
    sso_user_id: str = Field()
    email: str | None = Field(default=None, index=True)
    sso_last_login_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SSOConfig(SQLModel, table=True):  # type: ignore[call-arg]
    """SSO provider configuration (persisted in DB). Used by the SSO plugin.

    ``client_secret_encrypted`` is an at-rest ciphertext envelope and must never
    be returned by a read path. Consumers encrypt/decrypt it with the helpers in
    ``sso_secret``.
    """

    __tablename__ = "sso_config"
    __table_args__ = (Index("uq_sso_config_slug", "slug", unique=True),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    slug: str = Field(default_factory=_generate_sso_slug, description="Immutable URL-safe connection identifier")
    display_name: str = Field(description="Mutable admin-facing connection label")
    protocol: str = Field(default="oidc", description="Protocol discriminator for provider_settings")
    enabled: bool = Field(default=True)
    sort_order: int = Field(default=0, description="Login-button display order")
    client_secret_encrypted: str | None = Field(
        default=None,
        description="Versioned ciphertext envelope; never serialize in a read response",
    )
    provider_settings: SSOProviderSettings = Field(
        default_factory=OIDCProviderSettings,
        sa_column=Column(_ProviderSettingsJSON(), nullable=False),
    )
    email_claim: str = Field(default="email")
    username_claim: str = Field(default="preferred_username")
    user_id_claim: str = Field(default="sub")
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(), nullable=False, onupdate=_utc_now),
    )
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    updated_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    def __init__(self, **data: Any) -> None:
        slug = data.get("slug")
        if slug is not None and not _SSO_SLUG_PATTERN.fullmatch(slug):
            msg = "SSOConfig.slug must contain only lowercase letters, numbers, and single hyphens"
            raise ValueError(msg)
        protocol = data.get("protocol", "oidc")
        data["protocol"] = protocol
        data["provider_settings"] = _validate_provider_settings(
            protocol,
            data.get("provider_settings", OIDCProviderSettings()),
        )
        super().__init__(**data)

    @model_validator(mode="after")
    def validate_provider_settings_protocol(self) -> Self:
        self.provider_settings = _validate_provider_settings(self.protocol, self.provider_settings)
        return self

    @validates("client_secret_encrypted")
    def validate_client_secret_envelope(self, _key: str, value: str | None) -> str | None:
        """Reject plaintext or malformed client secrets on model writes."""
        if value is not None and not is_sso_client_secret_envelope(value):
            msg = "client_secret_encrypted must be a versioned SSO secret envelope"
            raise ValueError(msg)
        return value


class SSOSettings(SQLModel, table=True):  # type: ignore[call-arg]
    """Singleton instance-level SSO policy settings."""

    __tablename__ = "sso_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_sso_settings_singleton"),)

    id: int = Field(default=1, primary_key=True)
    enforce_sso: bool = Field(default=False)


@sa.event.listens_for(SSOConfig, "before_update")
def _prevent_sso_config_slug_update(
    _mapper: sa.orm.Mapper[SSOConfig],
    _connection: sa.Connection,
    target: SSOConfig,
) -> None:
    """Keep the connection identifier immutable after persistence."""
    if sa.inspect(target).attrs.slug.history.has_changes():
        msg = "SSOConfig.slug is immutable after insert"
        raise ValueError(msg)
