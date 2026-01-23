"""SSO configuration service that supports both file-based and database-based configs.

Priority order:
1. Database configuration (if exists and enabled)
2. File-based configuration (if SSO_CONFIG_FILE is set)
3. None (SSO disabled)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.auth.factory import AuthProvider
from langflow.services.auth.sso_config import OIDCConfig, SSOConfig, SSOConfigLoader, SSOProviderConfig

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.sso_config.model import SSOConfig as DBSSOConfig
    from langflow.services.settings.service import SettingsService

_DEFAULT_SCOPES_TUPLE = ("openid", "email", "profile")


class SSOConfigService:
    """Service for loading SSO configuration from multiple sources.

    Supports both file-based (YAML) and database-based configuration.
    Database config takes priority if both exist.
    """

    def __init__(self, settings_service: SettingsService):
        """Initialize SSO config service.

        Args:
            settings_service: Settings service instance
        """
        self.settings_service = settings_service
        self._file_config: SSOConfig | None = None
        self._file_config_loaded = False

    async def get_active_config(self, db: AsyncSession | None = None) -> SSOConfig | None:
        """Get the active SSO configuration.

        Priority order:
        1. Database config (if db session provided and config exists)
        2. File-based config (if SSO_CONFIG_FILE is set)
        3. None (SSO disabled)

        Args:
            db: Optional database session for loading DB config

        Returns:
            Active SSOConfig or None if SSO is not configured
        """
        auth_settings = self.settings_service.auth_settings

        # Check if SSO is enabled
        if not auth_settings.SSO_ENABLED:
            return None

        # Priority 1: Try database config
        if db is not None:
            db_config = await self._load_from_database(db)
            if db_config:
                logger.info("Using database-based SSO configuration")
                return db_config

        # Priority 2: Try file-based config
        if auth_settings.SSO_CONFIG_FILE:
            file_config = self._load_from_file(auth_settings.SSO_CONFIG_FILE)
            if file_config:
                logger.info(f"Using file-based SSO configuration from {auth_settings.SSO_CONFIG_FILE}")
                return file_config

        logger.warning("SSO is enabled but no configuration found (neither database nor file)")
        return None

    async def _load_from_database(self, db: AsyncSession) -> SSOConfig | None:
        """Load SSO config from database.

        Args:
            db: Database session

        Returns:
            SSOConfig converted from database model, or None
        """
        from langflow.services.database.models.sso_config.crud import get_active_sso_config

        try:
            db_config = await get_active_sso_config(db)
            if not db_config:
                return None

            # Convert database model to SSOConfig
            return self._db_config_to_sso_config(db_config)
        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Failed to load SSO config from database: {e}")
            return None

    def _load_from_file(self, config_path: str) -> SSOConfig | None:
        """Load SSO config from YAML file (cached).

        Args:
            config_path: Path to YAML config file

        Returns:
            SSOConfig from file, or None if loading fails
        """
        # Cache file config to avoid repeated file reads
        if not self._file_config_loaded:
            try:
                self._file_config = SSOConfigLoader.load_from_file(config_path)
                self._file_config_loaded = True
            except (FileNotFoundError, ValueError, OSError) as e:
                logger.error(f"Failed to load SSO config from file {config_path}: {e}")
                self._file_config = None
                self._file_config_loaded = True

        return self._file_config

    def _db_config_to_sso_config(self, db_config: DBSSOConfig) -> SSOConfig:
        """Convert database SSO config to SSOConfig model.

        Args:
            db_config: Database SSO configuration

        Returns:
            SSOConfig instance
        """
        # Build provider-specific config
        provider_config = None

        is_oidc = db_config.provider == "oidc"
        if is_oidc:
            provider_config = OIDCConfig(
                provider_name=db_config.provider_name,
                client_id=db_config.client_id or "",
                client_secret=db_config.client_secret_encrypted or "",  # Will be decrypted by auth service
                discovery_url=db_config.discovery_url or "",
                redirect_uri=db_config.redirect_uri or "",
                scopes=db_config.scopes.split() if db_config.scopes else list(_DEFAULT_SCOPES_TUPLE),
                email_claim=db_config.email_claim,
                username_claim=db_config.username_claim,
                user_id_claim=db_config.user_id_claim,
                token_endpoint=db_config.token_endpoint,
                authorization_endpoint=db_config.authorization_endpoint,
                jwks_uri=db_config.jwks_uri,
                issuer=db_config.issuer,
            )

        # Create SSOProviderConfig wrapper
        provider = SSOProviderConfig(
            id=db_config.provider_name.lower().replace(" ", "_"),  # Generate ID from provider name
            provider_type=AuthProvider(db_config.provider),
            enabled=db_config.enabled,
            oidc=provider_config if is_oidc else None,
            saml=None,  # TODO: Add SAML conversion when implementing SAML
            ldap=None,  # TODO: Add LDAP conversion when implementing LDAP
        )

        # Create SSOConfig with providers list
        return SSOConfig(
            enabled=db_config.enabled,
            enforce_sso=db_config.enforce_sso,
            providers=[provider],
        )

    def reload_file_config(self) -> None:
        """Force reload of file-based configuration.

        Useful when config file has been updated and needs to be reloaded.
        """
        self._file_config = None
        self._file_config_loaded = False
