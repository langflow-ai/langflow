import secrets
from pathlib import Path
from typing import Literal

from passlib.context import CryptContext
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from lfx.log.logger import logger
from lfx.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD
from lfx.services.settings.utils import read_secret_from_file, write_secret_to_file


class AuthSettings(BaseSettings):
    # Login settings
    CONFIG_DIR: str
    SECRET_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Secret key for JWT. If not provided, a random one will be generated.",
        frozen=False,
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 60 * 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 days

    # API Key to execute /process endpoint
    API_KEY_ALGORITHM: str = "HS256"
    API_V1_STR: str = "/api/v1"

    AUTO_LOGIN: bool = Field(
        default=True,  # TODO: Set to False in v2.0
        description=(
            "Enable automatic login with default credentials. "
            "SECURITY WARNING: This bypasses authentication and should only be used in development environments. "
            "Set to False in production. This will default to False in v2.0."
        ),
    )
    """If True, the application will attempt to log in automatically as a super user."""
    skip_auth_auto_login: bool = False
    """If True, the application will skip authentication when AUTO_LOGIN is enabled.
    This will be removed in v2.0"""

    WEBHOOK_AUTH_ENABLE: bool = False
    """If True, webhook endpoints will require API key authentication.
    If False, webhooks run as flow owner without authentication."""

    ENABLE_SUPERUSER_CLI: bool = Field(
        default=True,
        description="Allow creation of superusers via CLI. Set to False in production for security.",
    )
    """If True, allows creation of superusers via the CLI 'langflow superuser' command."""

    NEW_USER_IS_ACTIVE: bool = False
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

    pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")

    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_")

    def reset_credentials(self) -> None:
        # Preserve the configured username but scrub the password from memory to avoid plaintext exposure.
        self.SUPERUSER_PASSWORD = SecretStr("")

    # If autologin is true, then we need to set the credentials to
    # the default values
    # so we need to validate the superuser and superuser_password
    # fields
    @field_validator("SUPERUSER", "SUPERUSER_PASSWORD", mode="before")
    @classmethod
    def validate_superuser(cls, value, info):
        # When AUTO_LOGIN is enabled, force superuser to use default values.
        if info.data.get("AUTO_LOGIN"):
            logger.debug("Auto login is enabled, forcing superuser to use default values")
            if info.field_name == "SUPERUSER":
                if value != DEFAULT_SUPERUSER:
                    logger.debug("Resetting superuser to default value")
                return DEFAULT_SUPERUSER
            if info.field_name == "SUPERUSER_PASSWORD":
                if value != DEFAULT_SUPERUSER_PASSWORD.get_secret_value():
                    logger.debug("Resetting superuser password to default value")
                return DEFAULT_SUPERUSER_PASSWORD

        return value

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
        else:
            logger.debug("No secret key provided, generating a random one")

            if secret_key_path.exists():
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
