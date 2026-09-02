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
from urllib.parse import urlsplit
from uuid import uuid4

import sqlalchemy as sa
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, SecretStr, TypeAdapter, field_validator, model_validator
from pydantic import Field as PydanticField
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index
from sqlalchemy.orm import validates
from sqlalchemy.sql.naming import conv
from sqlmodel import Field, SQLModel
from typing_extensions import Self

from langflow.schema.serialize import UUIDstr
from langflow.services.database.models.auth.sso_secret import is_sso_client_secret_envelope

_SSO_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INVALID_PERCENT_ESCAPE_PATTERN = re.compile(r"%(?![0-9A-Fa-f]{2})")
_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)
_SSO_SECRET_ENVELOPE_HEADER = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:"  # noqa: S105  # pragma: allowlist secret
_SSO_SECRET_NONCE_LENGTH = 16
_SSO_SECRET_MIN_CIPHERTEXT_LENGTH = 22
_VALIDATED_UPDATE_FLAG = "_sso_validated_update_in_progress"
_OIDC_REMOTE_URL_FIELDS = (
    "discovery_url",
    "token_endpoint",
    "authorization_endpoint",
    "jwks_uri",
    "issuer",
)


def _generate_sso_slug() -> str:
    """Generate an opaque, URL-safe connection identifier."""
    return f"sso-{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OIDCProviderSettings(BaseModel):
    """OIDC-specific settings stored in ``sso_config.provider_settings``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["oidc"] = "oidc"
    discovery_url: str | None = None
    redirect_uri: str | None = None
    scopes: str | None = "openid email profile"
    token_endpoint: str | None = None
    authorization_endpoint: str | None = None
    jwks_uri: str | None = None
    issuer: str | None = None
    client_id: str | None = None

    @field_validator("client_id", mode="before")
    @classmethod
    def validate_client_id(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            msg = "OIDC client_id must not be blank"
            raise ValueError(msg)
        return value

    @field_validator(*_OIDC_REMOTE_URL_FIELDS, mode="before")
    @classmethod
    def validate_remote_url(cls, value: object, info: Any) -> object:
        """Require absolute HTTP(S) URLs for values consumed by the OIDC HTTP client."""
        if value is None or not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            msg = f"OIDC {info.field_name} must not be blank"
            raise ValueError(msg)
        is_http_url = False
        try:
            parsed = urlsplit(value)
            # urlsplit alone accepts malformed hosts and ports. Pydantic's URL
            # parser closes those gaps, while the pre-checks preserve the
            # original URL structure and reject invalid percent escapes rather
            # than normalizing them into a different URL.
            is_http_url = (
                parsed.scheme.lower() in {"http", "https"}
                and bool(parsed.netloc)
                and parsed.hostname is not None
                and not any(character.isspace() for character in value)
                and _INVALID_PERCENT_ESCAPE_PATTERN.search(value) is None
                and "%" not in parsed.hostname
            )
            if is_http_url:
                _ = parsed.port
                _HTTP_URL_ADAPTER.validate_python(value)
        except ValueError:
            is_http_url = False
        if not is_http_url:
            msg = f"OIDC {info.field_name} must be an absolute HTTP(S) URL"
            raise ValueError(msg)
        return value


class LegacyProviderSettings(BaseModel):
    """Read-compatible settings for disabled legacy SAML and LDAP rows.

    Langflow does not currently execute these protocols through this typed
    contract. Keeping their migrated values loadable avoids making an upgrade
    destructive; enabled legacy rows still fail closed below.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["saml", "ldap"]
    discovery_url: str | None = None
    redirect_uri: str | None = None
    scopes: str | None = None
    token_endpoint: str | None = None
    authorization_endpoint: str | None = None
    jwks_uri: str | None = None
    issuer: str | None = None
    client_id: str | None = None


# Add future protocol variants to this discriminated union. The database schema
# remains unchanged because every variant is stored in the same JSON column.
SSOProviderSettings: TypeAlias = Annotated[
    OIDCProviderSettings | LegacyProviderSettings,
    PydanticField(discriminator="protocol"),
]
_PROVIDER_SETTINGS_ADAPTER = TypeAdapter(SSOProviderSettings)


def _validate_provider_settings(protocol: str, value: object) -> SSOProviderSettings:
    settings = _PROVIDER_SETTINGS_ADAPTER.validate_python(value)
    if settings.protocol != protocol:
        msg = f"provider_settings protocol {settings.protocol!r} does not match sso_config.protocol {protocol!r}"
        raise ValueError(msg)
    return settings


def _validate_enabled_config(
    provider_settings: SSOProviderSettings,
    *,
    enabled: bool,
    has_client_secret: bool,
) -> None:
    if not enabled:
        return

    if provider_settings.protocol != "oidc":
        msg = "Only OIDC configurations can be enabled"
        raise ValueError(msg)

    if not provider_settings.client_id:
        msg = "Enabled OIDC configurations require a client_id"
        raise ValueError(msg)
    if not has_client_secret:
        msg = "Enabled OIDC configurations require a client secret"
        raise ValueError(msg)

    has_discovery = bool(provider_settings.discovery_url)
    has_explicit_endpoints = all(
        (
            provider_settings.authorization_endpoint,
            provider_settings.token_endpoint,
            provider_settings.jwks_uri,
        )
    )
    if not has_discovery and not has_explicit_endpoints:
        msg = (
            "Enabled OIDC configurations require discovery_url or authorization_endpoint, token_endpoint, and jwks_uri"
        )
        raise ValueError(msg)


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


class _SSOClientSecretEnvelope(sa.TypeDecorator):
    """Reject non-envelope values on every SQL bind path, including Core updates."""

    impl = sa.String
    cache_ok = True

    def process_bind_param(self, value: str | None, _dialect: sa.engine.Dialect) -> str | None:
        if value is not None and not is_sso_client_secret_envelope(value):
            msg = "client_secret_encrypted must be a versioned SSO secret envelope"
            raise ValueError(msg)
        return value


class SSOUserProfile(SQLModel, table=True):  # type: ignore[call-arg]
    """SSO profile per user.

    During the expand phase, ``sso_provider`` can contain a legacy provider name,
    an OSS ``EXTERNAL_AUTH_PROVIDER`` key, or the immutable ``SSOConfig.slug``.
    SSO plugins must dual-read names and slugs until a later contract migration;
    no database foreign key is intentionally enforced.
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
    sso_provider: str = Field(description="SSO connection slug or expand-phase legacy provider key")
    sso_user_id: str = Field()
    email: str | None = Field(default=None, index=True)
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)
    picture: str | None = Field(default=None)
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
    enabled: bool = Field(default=False)
    sort_order: int = Field(default=0, description="Login-button display order")
    client_secret_encrypted: str | None = Field(
        default=None,
        exclude=True,
        repr=False,
        sa_column=Column(_SSOClientSecretEnvelope(), nullable=True),
        description="Versioned ciphertext envelope; never serialize in a read response",
    )
    provider_settings: SSOProviderSettings = Field(
        default_factory=OIDCProviderSettings,
        sa_column=Column(_ProviderSettingsJSON(), nullable=False),
        description=(
            "Validated provider settings persisted as JSON. Assign a new object "
            "(or call flag_modified) to persist changes; in-place nested field "
            "mutations are not tracked by SQLAlchemy."
        ),
    )
    email_claim: str = Field(default="email")
    username_claim: str = Field(default="preferred_username")
    user_id_claim: str = Field(default="sub")
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=_utc_now),
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
        _validate_enabled_config(
            self.provider_settings,
            enabled=self.enabled,
            has_client_secret=self.client_secret_encrypted is not None,
        )

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        """Validate without assigning through SQLAlchemy instrumentation."""
        provider_settings = _validate_provider_settings(self.protocol, self.provider_settings)
        _validate_enabled_config(
            provider_settings,
            enabled=self.enabled,
            has_client_secret=self.client_secret_encrypted is not None,
        )
        return self

    @field_validator("slug")
    @classmethod
    def validate_slug_field(cls, value: str) -> str:
        if not _SSO_SLUG_PATTERN.fullmatch(value):
            msg = "SSOConfig.slug must contain only lowercase letters, numbers, and single hyphens"
            raise ValueError(msg)
        return value

    @field_validator("client_secret_encrypted")
    @classmethod
    def validate_client_secret_field(cls, value: str | None) -> str | None:
        if value is not None and not is_sso_client_secret_envelope(value):
            msg = "client_secret_encrypted must be a versioned SSO secret envelope"
            raise ValueError(msg)
        return value

    @validates("slug")
    def validate_slug_assignment(self, _key: str, value: str) -> str:
        """Reject invalid slugs assigned before the first insert."""
        if not _SSO_SLUG_PATTERN.fullmatch(value):
            msg = "SSOConfig.slug must contain only lowercase letters, numbers, and single hyphens"
            raise ValueError(msg)
        return value

    @validates("protocol")
    def validate_protocol(self, _key: str, value: str) -> str:
        """Keep protocol aligned with provider_settings on attribute assignment."""
        # Use __dict__ so we do not assume the counterpart is loaded yet (e.g. DB hydrate).
        if not self.__dict__.get(_VALIDATED_UPDATE_FLAG) and "provider_settings" in self.__dict__:
            _validate_provider_settings(value, self.__dict__["provider_settings"])
        return value

    @validates("provider_settings")
    def validate_provider_settings(
        self,
        _key: str,
        value: SSOProviderSettings | dict[str, Any],
    ) -> SSOProviderSettings:
        """Keep provider_settings aligned with protocol on attribute assignment."""
        if not self.__dict__.get(_VALIDATED_UPDATE_FLAG) and "protocol" in self.__dict__:
            return _validate_provider_settings(self.__dict__["protocol"], value)
        return _PROVIDER_SETTINGS_ADAPTER.validate_python(value)

    @validates("client_secret_encrypted")
    def validate_client_secret_envelope(self, _key: str, value: str | None) -> str | None:
        """Reject plaintext or malformed client secrets on model writes."""
        if value is not None and not is_sso_client_secret_envelope(value):
            msg = "client_secret_encrypted must be a versioned SSO secret envelope"
            raise ValueError(msg)
        return value

    @validates("enabled")
    def validate_enabled_assignment(self, _key: str, value: bool) -> bool:  # noqa: FBT001
        """Fail closed when an existing configuration is enabled by assignment."""
        provider_settings = self.__dict__.get("provider_settings")
        if value and provider_settings is not None and not self.__dict__.get(_VALIDATED_UPDATE_FLAG):
            _validate_enabled_config(
                provider_settings,
                enabled=True,
                has_client_secret=self.__dict__.get("client_secret_encrypted") is not None,
            )
        return value


def _nonblank_json_string(json_column: sa.Column[Any], key: str) -> sa.ColumnElement[bool]:
    value = json_column[key].as_string()
    return sa.and_(value.is_not(None), sa.func.length(sa.func.trim(value)) > 0)


def _http_json_url_or_null(json_column: sa.Column[Any], key: str) -> sa.ColumnElement[bool]:
    value = json_column[key].as_string()
    normalized = sa.func.lower(value)
    no_whitespace = sa.and_(
        *(sa.func.length(value) == sa.func.length(sa.func.replace(value, character, "")) for character in " \t\r\n")
    )
    http_url = sa.and_(
        normalized.like("http://%"),
        sa.func.length(value) > len("http://"),
        sa.func.substr(value, len("http://") + 1, 1).not_in(("/", "\\", "?", "#", ":")),
        no_whitespace,
    )
    https_url = sa.and_(
        normalized.like("https://%"),
        sa.func.length(value) > len("https://"),
        sa.func.substr(value, len("https://") + 1, 1).not_in(("/", "\\", "?", "#", ":")),
        no_whitespace,
    )
    return sa.or_(value.is_(None), http_url, https_url)


def _client_secret_envelope_or_null(value: sa.Column[Any]) -> sa.ColumnElement[bool]:
    string_value = sa.type_coerce(value, sa.String())
    separator_position = len(_SSO_SECRET_ENVELOPE_HEADER) + _SSO_SECRET_NONCE_LENGTH + 1
    minimum_length = separator_position + _SSO_SECRET_MIN_CIPHERTEXT_LENGTH
    return sa.or_(
        value.is_(None),
        sa.and_(
            sa.func.substr(string_value, 1, len(_SSO_SECRET_ENVELOPE_HEADER)) == _SSO_SECRET_ENVELOPE_HEADER,
            sa.func.substr(string_value, separator_position, 1) == ":",
            sa.func.length(string_value) >= minimum_length,
        ),
    )


def _install_sso_config_database_invariants() -> None:
    """Install portable checks and dialect-specific slug immutability triggers."""
    table = SSOConfig.__table__
    provider_settings = table.c.provider_settings
    protocol = table.c.protocol
    enabled = table.c.enabled

    # conv() marks these as final names so alembic's ck_%(table_name)s_%(constraint_name)s
    # convention (applied in alembic/env.py) does not double-prefix them.
    table.append_constraint(
        CheckConstraint(
            sa.and_(
                protocol.in_(("oidc", "saml", "ldap")),
                provider_settings["protocol"].as_string().is_not(None),
                provider_settings["protocol"].as_string() == protocol,
            ),
            name=conv("ck_sso_config_protocol_consistency"),
        )
    )
    table.append_constraint(
        CheckConstraint(
            sa.or_(
                enabled.is_(False),
                protocol.in_(("saml", "ldap")),
                sa.and_(
                    protocol == "oidc",
                    table.c.client_secret_encrypted.is_not(None),
                    _nonblank_json_string(provider_settings, "client_id"),
                    sa.or_(
                        _nonblank_json_string(provider_settings, "discovery_url"),
                        sa.and_(
                            _nonblank_json_string(provider_settings, "authorization_endpoint"),
                            _nonblank_json_string(provider_settings, "token_endpoint"),
                            _nonblank_json_string(provider_settings, "jwks_uri"),
                        ),
                    ),
                    *(_http_json_url_or_null(provider_settings, key) for key in _OIDC_REMOTE_URL_FIELDS),
                ),
            ),
            name=conv("ck_sso_config_enabled_complete"),
        )
    )
    table.append_constraint(
        CheckConstraint(
            _client_secret_envelope_or_null(table.c.client_secret_encrypted),
            name=conv("ck_sso_config_client_secret_envelope"),
        )
    )

    sqlite_trigger = sa.DDL(
        """
        CREATE TRIGGER trg_sso_config_slug_immutable
        BEFORE UPDATE OF slug ON sso_config
        FOR EACH ROW
        WHEN OLD.slug IS NOT NULL AND NEW.slug IS NOT OLD.slug
        BEGIN
            SELECT RAISE(ABORT, 'SSOConfig.slug is immutable after insert');
        END
        """
    ).execute_if(dialect="sqlite")
    postgres_trigger_function = sa.DDL(
        """
        CREATE OR REPLACE FUNCTION prevent_sso_config_slug_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.slug IS NOT NULL AND NEW.slug IS DISTINCT FROM OLD.slug THEN
                RAISE EXCEPTION 'SSOConfig.slug is immutable after insert';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    ).execute_if(dialect="postgresql")
    postgres_trigger = sa.DDL(
        """
        CREATE TRIGGER trg_sso_config_slug_immutable
        BEFORE UPDATE OF slug ON sso_config
        FOR EACH ROW EXECUTE FUNCTION prevent_sso_config_slug_update()
        """
    ).execute_if(dialect="postgresql")
    drop_postgres_function = sa.DDL("DROP FUNCTION IF EXISTS prevent_sso_config_slug_update()").execute_if(
        dialect="postgresql"
    )
    sa.event.listen(table, "after_create", sqlite_trigger)
    sa.event.listen(table, "after_create", postgres_trigger_function)
    sa.event.listen(table, "after_create", postgres_trigger)
    sa.event.listen(table, "after_drop", drop_postgres_function)


_install_sso_config_database_invariants()


class SSOConfigCreate(SQLModel):
    """Validated external input for creating an SSO configuration."""

    model_config = ConfigDict(extra="forbid")

    display_name: str
    protocol: Literal["oidc"] = "oidc"
    enabled: bool = False
    sort_order: int = 0
    client_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    provider_settings: SSOProviderSettings = Field(default_factory=OIDCProviderSettings)
    email_claim: str = "email"
    username_claim: str = "preferred_username"
    user_id_claim: str = "sub"

    @field_validator("client_secret")
    @classmethod
    def validate_client_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            msg = "SSO client secret must not be blank"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        provider_settings = _validate_provider_settings(self.protocol, self.provider_settings)
        _validate_enabled_config(
            provider_settings,
            enabled=self.enabled,
            has_client_secret=self.client_secret is not None,
        )
        return self

    def to_model(
        self,
        settings_service: Any | None = None,
        *,
        actor_id: UUIDstr | None = None,
    ) -> SSOConfig:
        """Build the persistence model, encrypting plaintext before it reaches the table."""
        from langflow.services.database.models.auth.sso_secret import encrypt_sso_client_secret

        values = self.model_dump(exclude={"client_secret"})
        if self.client_secret is not None:
            values["client_secret_encrypted"] = encrypt_sso_client_secret(
                self.client_secret.get_secret_value(),
                settings_service,
            )
        values["created_by"] = actor_id
        values["updated_by"] = actor_id
        return SSOConfig(**values)


class SSOConfigRead(SQLModel):
    """Secret-free representation of a persisted SSO configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: UUIDstr
    slug: str
    display_name: str
    protocol: str
    enabled: bool
    sort_order: int
    provider_settings: SSOProviderSettings
    email_claim: str
    username_claim: str
    user_id_claim: str
    created_at: datetime
    updated_at: datetime
    created_by: UUIDstr | None
    updated_by: UUIDstr | None


class SSOConfigUpdate(SQLModel):
    """Validated partial update input for an SSO configuration."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    protocol: Literal["oidc"] | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    client_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    provider_settings: SSOProviderSettings | None = None
    email_claim: str | None = None
    username_claim: str | None = None
    user_id_claim: str | None = None

    @field_validator("client_secret")
    @classmethod
    def validate_client_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            msg = "SSO client secret must not be blank"
            raise ValueError(msg)
        return value

    def apply_to(
        self,
        config: SSOConfig,
        settings_service: Any | None = None,
        *,
        actor_id: UUIDstr | None = None,
    ) -> SSOConfig:
        """Validate the merged state and apply this update to a persistence model."""
        from langflow.services.database.models.auth.sso_secret import encrypt_sso_client_secret

        values = self.model_dump(exclude_unset=True, exclude={"client_secret"})
        if "provider_settings" in self.model_fields_set:
            values["provider_settings"] = self.provider_settings
        required_fields = {
            "display_name",
            "protocol",
            "enabled",
            "sort_order",
            "provider_settings",
            "email_claim",
            "username_claim",
            "user_id_claim",
        }
        null_fields = sorted(field for field in required_fields if field in values and values[field] is None)
        if null_fields:
            msg = f"SSO configuration fields cannot be null: {', '.join(null_fields)}"
            raise ValueError(msg)

        protocol = values.get("protocol", config.protocol)
        provider_settings = _validate_provider_settings(
            protocol,
            values.get("provider_settings", config.provider_settings),
        )
        enabled = values.get("enabled", config.enabled)

        encrypted_secret = config.client_secret_encrypted
        if "client_secret" in self.model_fields_set:
            encrypted_secret = (
                encrypt_sso_client_secret(self.client_secret.get_secret_value(), settings_service)
                if self.client_secret is not None
                else None
            )
        _validate_enabled_config(
            provider_settings,
            enabled=enabled,
            has_client_secret=encrypted_secret is not None,
        )

        # Apply dependencies before ``enabled`` so assignment-time validation
        # observes the already-validated merged state instead of the old,
        # potentially incomplete configuration.
        enabled_was_set = "enabled" in values
        enabled_value = values.pop("enabled") if enabled_was_set else config.enabled
        config.__dict__[_VALIDATED_UPDATE_FLAG] = True
        try:
            for field_name, value in values.items():
                setattr(config, field_name, value)
            if "client_secret" in self.model_fields_set:
                config.client_secret_encrypted = encrypted_secret
            if enabled_was_set:
                config.enabled = enabled_value
        finally:
            config.__dict__.pop(_VALIDATED_UPDATE_FLAG, None)

        # Assert the persisted object matches the state validated above; the
        # before-update hook repeats this check at flush time as defense in depth.
        _validate_enabled_config(
            _validate_provider_settings(config.protocol, config.provider_settings),
            enabled=config.enabled,
            has_client_secret=config.client_secret_encrypted is not None,
        )
        if actor_id is not None:
            config.updated_by = actor_id
        return config


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
    _validate_enabled_config(
        _validate_provider_settings(target.protocol, target.provider_settings),
        enabled=target.enabled,
        has_client_secret=target.client_secret_encrypted is not None,
    )


@sa.event.listens_for(SSOConfig, "before_insert")
def _validate_sso_config_before_insert(
    _mapper: sa.orm.Mapper[SSOConfig],
    _connection: sa.Connection,
    target: SSOConfig,
) -> None:
    """Validate cross-column invariants before ORM inserts."""
    _validate_enabled_config(
        _validate_provider_settings(target.protocol, target.provider_settings),
        enabled=target.enabled,
        has_client_secret=target.client_secret_encrypted is not None,
    )
