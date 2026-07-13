import secrets
from enum import Enum
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from passlib.context import CryptContext
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from lfx.log.logger import logger
from lfx.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD
from lfx.services.settings.utils import (
    derive_public_key_from_private,
    generate_rsa_key_pair,
    read_secret_from_file,
    write_public_key_to_file,
    write_secret_to_file,
)


class JWTAlgorithm(str, Enum):
    """JWT signing algorithm options."""

    HS256 = "HS256"
    RS256 = "RS256"
    RS512 = "RS512"

    def is_asymmetric(self) -> bool:
        """Return True if this algorithm uses asymmetric (public/private key) cryptography."""
        return self in (JWTAlgorithm.RS256, JWTAlgorithm.RS512)


class AuthSettings(BaseSettings):
    # Login settings
    CONFIG_DIR: str
    SECRET_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Secret key for JWT (used with HS256). If not provided, a random one will be generated.",
        frozen=False,
    )
    PRIVATE_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="RSA private key for JWT signing (RS256/RS512). Auto-generated if not provided.",
        frozen=False,
    )
    PUBLIC_KEY: str = Field(
        default="",
        description="RSA public key for JWT verification (RS256/RS512). Derived from private key if not provided.",
    )
    ALGORITHM: JWTAlgorithm = Field(
        default=JWTAlgorithm.HS256,
        description="JWT signing algorithm. Use RS256 or RS512 for asymmetric signing (recommended for production).",
    )
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 60 * 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 days

    # API Key to execute /process endpoint
    API_KEY_ALGORITHM: str = "HS256"
    API_V1_STR: str = "/api/v1"

    # API Key Source Configuration
    API_KEY_SOURCE: Literal["db", "env"] = Field(
        default="db",
        description=(
            "Source for API key validation. "
            "'db' validates against database-stored API keys (default behavior). "
            "'env' validates against the LANGFLOW_API_KEY environment variable."
        ),
    )

    AUTO_LOGIN: bool = Field(
        default=True,  # TODO: Set to False in v2.0
        description=(
            "Enable automatic login with a configured or generated bootstrap account. "
            "SECURITY WARNING: This bypasses authentication and should only be used in development environments. "
            "Set to False in production. This will default to False in v2.0."
        ),
    )
    """If True, the application will attempt to log in automatically as a super user."""
    skip_auth_auto_login: bool = False
    """If True, the application will skip authentication when AUTO_LOGIN is enabled.
    This will be removed in v2.0"""

    WEBHOOK_AUTH_ENABLE: bool = True
    """If True, webhook endpoints will require API key authentication.
    If False, webhooks run as flow owner without authentication.
    Defaults to True for secure-by-default behavior; set to False only in
    trusted environments where unauthenticated webhook execution is acceptable."""

    ENABLE_SUPERUSER_CLI: bool = Field(
        default=True,
        description="Allow creation of superusers via CLI. Set to False in production for security.",
    )
    """If True, allows creation of superusers via the CLI 'langflow superuser' command."""

    NEW_USER_IS_ACTIVE: bool = False

    ENABLE_SIGNUP: bool = Field(
        default=True,
        description=(
            "Whether public self-registration via POST /api/v1/users/ is allowed. "
            "Always refused when AUTO_LOGIN is enabled (single-user mode has no signup "
            "concept); operators running multi-user instances can set this to False to "
            "disable public sign up entirely. Authenticated superusers can still create "
            "users regardless of this setting."
        ),
    )
    """If True, public self-registration via POST /api/v1/users/ is allowed."""

    SUPERUSER: str = DEFAULT_SUPERUSER
    # Store password as SecretStr to prevent accidental plaintext exposure
    SUPERUSER_PASSWORD: SecretStr = Field(default=DEFAULT_SUPERUSER_PASSWORD)

    REFRESH_SAME_SITE: Literal["lax", "strict", "none"] = "none"
    """The SameSite attribute of the refresh token cookie."""
    REFRESH_SECURE: bool = True
    """The Secure attribute of the refresh token cookie."""
    REFRESH_HTTPONLY: bool = True
    """The HttpOnly attribute of the refresh token cookie."""
    ACCESS_SAME_SITE: Literal["lax", "strict", "none"] = "lax"
    """The SameSite attribute of the access token cookie."""
    ACCESS_SECURE: bool = False
    """The Secure attribute of the access token cookie."""
    ACCESS_HTTPONLY: bool = False
    """The HttpOnly attribute of the access token cookie."""

    COOKIE_DOMAIN: str | None = None
    """The domain attribute of the cookies. If None, the domain is not set."""

    # SSO Feature Flags
    SSO_ENABLED: bool = Field(
        default=False,
        description="Enable SSO authentication. Disabled by default. Set to true to enable SSO.",
    )
    """If True, SSO authentication is enabled. Configuration must be provided via SSO_CONFIG_FILE."""

    SSO_PROVIDER: str = Field(
        default="jwt",
        description="SSO provider type: jwt (default), oidc, saml, ldap",
    )
    """The authentication provider to use. Default is 'jwt' for standard authentication."""

    SSO_CONFIG_FILE: str | None = Field(
        default=None,
        description="Path to SSO configuration file (YAML format). Required when SSO_ENABLED=true.",
    )
    """Path to YAML configuration file for SSO settings. Contains provider-specific configuration."""

    # External trusted-identity settings.
    # Used when an upstream identity layer (proxy, gateway, IdP) issues or
    # validates a credential and Langflow needs to accept it and map it to
    # a local user via SSOUserProfile (JIT provisioning).
    EXTERNAL_AUTH_ENABLED: bool = Field(
        default=False,
        description="Enable trusted external request authentication and JIT local user mapping.",
    )
    EXTERNAL_AUTH_PROVIDER: str = Field(
        default="external",
        description="Stable provider key written to SSOUserProfile.sso_provider for external identities.",
    )
    EXTERNAL_AUTH_TOKEN_HEADER: str = Field(
        default="Authorization",
        description=(
            "Header containing the external credential. The native Langflow JWT path is tried first; "
            "if it fails, the external path is attempted as a fallback. Bearer-prefixed values are supported."
        ),
    )
    EXTERNAL_AUTH_TOKEN_COOKIE: str | None = Field(
        default=None,
        description="Optional cookie name containing the external credential.",
    )
    EXTERNAL_AUTH_IDENTITY_RESOLVER: str | None = Field(
        default=None,
        description=(
            "Optional 'module:attribute' import path for a custom resolver that converts the external "
            "credential into an identity. Defaults to built-in JWT validation when unset."
        ),
    )
    EXTERNAL_AUTH_TRUSTED_JWT_DECODE: bool = Field(
        default=False,
        description=(
            "When True, decode the external JWT without verifying its signature. ONLY safe behind a trusted "
            "upstream proxy that already validates the token. Off by default."
        ),
    )
    EXTERNAL_AUTH_JWKS_URL: str | None = Field(
        default=None,
        description="JWKS URL used to verify external JWT signatures when trusted decode is disabled.",
    )
    EXTERNAL_AUTH_ISSUER: str | None = Field(
        default=None,
        description="Expected JWT issuer (iss). Leave empty to skip issuer validation.",
    )
    EXTERNAL_AUTH_AUDIENCE: str | None = Field(
        default=None,
        description="Expected JWT audience (aud). Comma-separated audiences are supported.",
    )
    EXTERNAL_AUTH_ALGORITHMS: str = Field(
        default="RS256",
        description="Comma-separated JWT algorithms accepted for external JWT validation.",
    )
    EXTERNAL_AUTH_SUBJECT_CLAIM: str = Field(
        default="sub",
        description="JWT claim used as the stable external user id.",
    )
    EXTERNAL_AUTH_USERNAME_CLAIM: str = Field(
        default="preferred_username",
        description="JWT claim preferred for the local Langflow username on JIT provisioning.",
    )
    EXTERNAL_AUTH_EMAIL_CLAIM: str = Field(
        default="email",
        description="JWT claim containing the user's email.",
    )
    EXTERNAL_AUTH_NAME_CLAIM: str = Field(
        default="name",
        description="JWT claim containing the user's display name.",
    )
    EXTERNAL_AUTH_ACCESS_CEILING_ENABLED: bool = Field(
        default=False,
        description=(
            "Enable a coarse deny-only action ceiling for users authenticated by external trusted identity. "
            "This is not an RBAC engine; it only caps actions above a mapped access level."
        ),
    )
    EXTERNAL_AUTH_ACCESS_CLAIM: str | None = Field(
        default=None,
        description=(
            "JWT claim used to derive the external access ceiling. Claim values are mapped through "
            "EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING."
        ),
    )
    EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING: str | None = Field(
        default=None,
        description=(
            "JSON object or comma-separated value map from external claim values to one of: viewer, editor, admin. "
            'Example: \'{"view":"viewer","edit":"editor"}\'. Built-in aliases cover common values.'
        ),
    )
    EXTERNAL_AUTH_DEFAULT_ACCESS_LEVEL: str = Field(
        default="viewer",
        description="Fallback access level used when the access claim is missing or unmapped.",
    )
    EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS: bool = Field(
        default=True,
        description=(
            "When the external access ceiling is enabled, reject Langflow API-key authentication for users mapped "
            "through the configured external provider so API keys cannot bypass the JWT claim ceiling."
        ),
    )

    # Authorization (RBAC) feature flags — enforcement via authorization_service plugin
    AUTHZ_ENABLED: bool = Field(
        default=False,
        description="Enable authorization enforcement. Requires an authorization_service plugin.",
    )
    AUTHZ_SUPERUSER_BYPASS: bool = Field(
        default=True,
        description="When True, active superusers bypass authorization checks (audited by the plugin).",
    )
    AUTHZ_AUDIT_ENABLED: bool = Field(
        default=False,
        description=(
            "Write an AuthzAuditLog row for every authorization decision and share-administration "
            "action. Independent of AUTHZ_ENABLED — set this to True while enforcement is off to "
            "observe traffic before flipping the AUTHZ_ENABLED flag. Defaults to False because the "
            "fire-and-forget audit task opens its own DB session per row; on SQLite this can "
            "contend with concurrent write transactions ('database is locked')."
        ),
    )
    AUTHZ_AUDIT_RETENTION_DAYS: int = Field(
        default=90,
        ge=0,
        description=(
            "Number of days to retain rows in ``authz_audit_log``. Older rows are deleted on "
            "startup and by the periodic cleanup task. Set to 0 to disable retention pruning "
            "(append-only — the table will grow without bound; pair with an external archival "
            "or partitioning job). The default of 90 days bounds steady-state size for typical "
            "enterprise deployments."
        ),
    )
    AUTHZ_AUDIT_CLEANUP_INTERVAL: int = Field(
        default=86400,
        ge=300,
        description=(
            "Seconds between scheduled ``authz_audit_log`` retention sweeps. A sweep runs once at "
            "startup; thereafter a background worker prunes rows older than "
            "AUTHZ_AUDIT_RETENTION_DAYS every interval so a long-running instance stays bounded "
            "between restarts. The worker only runs when AUTHZ_AUDIT_ENABLED is True and "
            "AUTHZ_AUDIT_RETENTION_DAYS > 0. Default 86400 (daily); minimum 300 (5 minutes)."
        ),
    )

    pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")

    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_")

    def reset_credentials(self) -> None:
        # Preserve the configured username but scrub the password from memory to avoid plaintext exposure.
        self.SUPERUSER_PASSWORD = SecretStr("")

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def get_secret_key(cls, value, info):
        config_dir = info.data.get("CONFIG_DIR")

        if not config_dir:
            logger.debug("No CONFIG_DIR provided, not saving secret key")
            return value or secrets.token_urlsafe(32)

        secret_key_path = Path(config_dir) / "secret_key"

        if value:
            logger.debug("Secret key provided")
            secret_value = value.get_secret_value() if isinstance(value, SecretStr) else value
            write_secret_to_file(secret_key_path, secret_value)
        elif secret_key_path.exists():
            value = read_secret_from_file(secret_key_path)
            logger.debug("Loaded secret key")
            if not value:
                value = secrets.token_urlsafe(32)
                write_secret_to_file(secret_key_path, value)
                logger.debug("Saved secret key")
        else:
            value = secrets.token_urlsafe(32)
            write_secret_to_file(secret_key_path, value)
            logger.debug("Saved secret key")

        return value if isinstance(value, SecretStr) else SecretStr(value).get_secret_value()

    @field_validator("EXTERNAL_AUTH_PROVIDER", mode="before")
    @classmethod
    def normalize_external_auth_provider(cls, value):
        """Normalize the external provider key once at the config boundary.

        Every consumer (JIT provisioning, the API-key floor in the auth service,
        SSOUserProfile.sso_provider lookups) reads this value directly, so an
        empty/whitespace value must resolve to the same canonical string here.
        Otherwise the value written ("external") and the value compared against
        ("") would diverge and silently disable a security floor.
        """
        if value is None:
            return "external"
        normalized = str(value).strip()
        return normalized or "external"

    @field_validator("EXTERNAL_AUTH_JWKS_URL", mode="before")
    @classmethod
    def validate_external_auth_jwks_url(cls, value):
        """Reject non-HTTPS JWKS URLs to stop a network MITM swapping signing keys.

        An ``http://`` JWKS endpoint lets an on-path attacker substitute their own
        keys and forge tokens. HTTPS is required; ``http`` is permitted only for
        loopback hosts (localhost / 127.0.0.1 / ::1) to keep local development
        usable.
        """
        if value is None:
            return value
        url = str(value).strip()
        if not url:
            return None

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme == "https":
            return url
        if scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            return url

        msg = (
            "EXTERNAL_AUTH_JWKS_URL must use https so a network attacker cannot swap the JWKS "
            "signing keys and forge tokens. http is allowed only for localhost/127.0.0.1/::1."
        )
        raise ValueError(msg)

    @model_validator(mode="after")
    def setup_rsa_keys(self):
        """Generate or load RSA keys when using RS256/RS512 algorithm."""
        if not self.ALGORITHM.is_asymmetric():
            return self

        config_dir = self.CONFIG_DIR
        private_key_value = self.PRIVATE_KEY.get_secret_value() if self.PRIVATE_KEY else ""

        if not config_dir:
            # No config dir - generate keys in memory if not provided
            if not private_key_value:
                logger.debug("No CONFIG_DIR provided, generating RSA keys in memory")
                private_key_pem, public_key_pem = generate_rsa_key_pair()
                object.__setattr__(self, "PRIVATE_KEY", SecretStr(private_key_pem))
                object.__setattr__(self, "PUBLIC_KEY", public_key_pem)
            elif not self.PUBLIC_KEY:
                # Derive public key from private key
                public_key_pem = derive_public_key_from_private(private_key_value)
                object.__setattr__(self, "PUBLIC_KEY", public_key_pem)
            return self

        private_key_path = Path(config_dir) / "private_key.pem"
        public_key_path = Path(config_dir) / "public_key.pem"

        if private_key_value:
            # Private key provided via env var - save it and derive public key
            logger.debug("RSA private key provided")
            write_secret_to_file(private_key_path, private_key_value)

            if not self.PUBLIC_KEY:
                public_key_pem = derive_public_key_from_private(private_key_value)
                object.__setattr__(self, "PUBLIC_KEY", public_key_pem)
                write_public_key_to_file(public_key_path, public_key_pem)
        # No private key provided - load from file or generate
        elif private_key_path.exists():
            logger.debug("Loading RSA keys from files")
            private_key_pem = read_secret_from_file(private_key_path)
            object.__setattr__(self, "PRIVATE_KEY", SecretStr(private_key_pem))

            if public_key_path.exists():
                public_key_pem = public_key_path.read_text(encoding="utf-8")
                object.__setattr__(self, "PUBLIC_KEY", public_key_pem)
            else:
                # Derive public key from private key
                public_key_pem = derive_public_key_from_private(private_key_pem)
                object.__setattr__(self, "PUBLIC_KEY", public_key_pem)
                write_public_key_to_file(public_key_path, public_key_pem)
        else:
            # Generate new RSA key pair
            logger.debug("Generating new RSA key pair")
            private_key_pem, public_key_pem = generate_rsa_key_pair()
            write_secret_to_file(private_key_path, private_key_pem)
            write_public_key_to_file(public_key_path, public_key_pem)
            object.__setattr__(self, "PRIVATE_KEY", SecretStr(private_key_pem))
            object.__setattr__(self, "PUBLIC_KEY", public_key_pem)
            logger.debug("RSA key pair generated and saved")

        return self
