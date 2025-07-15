from __future__ import annotations

from langflow.services.base import Service
from langflow.services.settings.auth import AuthSettings
from langflow.services.settings.base import Settings
from langflow.services.settings.categories import (
    DatabaseSettings,
    RedisSettings,
    ServerSettings,
    TelemetrySettings,
)


class SettingsService(Service):
    name = "settings_service"

    def __init__(self, settings: Settings, auth_settings: AuthSettings):
        super().__init__()
        self.settings: Settings = settings
        self.auth_settings: AuthSettings = auth_settings

        # Cache for categorized settings
        self._database_settings: DatabaseSettings | None = None
        self._redis_settings: RedisSettings | None = None
        self._server_settings: ServerSettings | None = None
        self._telemetry_settings: TelemetrySettings | None = None

        # Build attribute mapping for O(1) lookup
        self._attribute_mapping: dict[str, str] = {}
        self._build_attribute_mapping()

    def _build_attribute_mapping(self) -> None:
        """Build mapping of attribute names to their category for O(1) lookup."""
        # Map database settings
        database_fields = DatabaseSettings.model_fields.keys()
        for field in database_fields:
            self._attribute_mapping[field] = "database"

        # Map redis settings
        redis_fields = RedisSettings.model_fields.keys()
        for field in redis_fields:
            self._attribute_mapping[field] = "redis"

        # Map server settings
        server_fields = ServerSettings.model_fields.keys()
        for field in server_fields:
            self._attribute_mapping[field] = "server"

        # Map telemetry settings
        telemetry_fields = TelemetrySettings.model_fields.keys()
        for field in telemetry_fields:
            self._attribute_mapping[field] = "telemetry"

    def _get_category_for_attribute(self, name: str) -> str | None:
        """Get the category for a given attribute name in O(1) time."""
        return self._attribute_mapping.get(name)

    def _invalidate_cache(self) -> None:
        """Invalidate cached categorized settings."""
        self._database_settings = None
        self._redis_settings = None
        self._server_settings = None
        self._telemetry_settings = None

    # ---------------------------------------------------------------------
    # Convenience accessors for grouped settings with caching
    # ---------------------------------------------------------------------
    @property
    def database(self) -> DatabaseSettings:
        """Return database-related settings."""
        if self._database_settings is None:
            self._database_settings = DatabaseSettings(**self.settings.model_dump())
        return self._database_settings

    @property
    def redis(self) -> RedisSettings:
        """Return redis-related settings."""
        if self._redis_settings is None:
            self._redis_settings = RedisSettings(**self.settings.model_dump())
        return self._redis_settings

    @property
    def server(self) -> ServerSettings:
        """Return web-server settings."""
        if self._server_settings is None:
            self._server_settings = ServerSettings(**self.settings.model_dump())
        return self._server_settings

    @property
    def telemetry(self) -> TelemetrySettings:
        """Return telemetry settings."""
        if self._telemetry_settings is None:
            self._telemetry_settings = TelemetrySettings(**self.settings.model_dump())
        return self._telemetry_settings

    # ---------------------------------------------------------------------
    # Django-like attribute access
    # ---------------------------------------------------------------------
    def __getattr__(self, name: str):
        """Django-like attribute access for settings."""
        if name.startswith("_"):
            msg = f"'{self.__class__.__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)

        # Check if it's a categorized setting
        category = self._get_category_for_attribute(name)
        if category:
            category_obj = getattr(self, category)
            if hasattr(category_obj, name):
                return getattr(category_obj, name)

        # Check if it's in the main settings
        if hasattr(self.settings, name):
            return getattr(self.settings, name)

        # Check if it's in auth settings
        if hasattr(self.auth_settings, name):
            return getattr(self.auth_settings, name)

        msg = f"'{self.__class__.__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    def __setattr__(self, name: str, value):
        """Django-like attribute setting for settings."""
        if name.startswith("_") or name in ("settings", "auth_settings"):
            super().__setattr__(name, value)
            return

        # Check if it's a categorized setting
        category = self._get_category_for_attribute(name)
        if category and hasattr(self.settings, name):
            setattr(self.settings, name, value)
            self._invalidate_cache()
            return

        # Check if it's in the main settings
        if hasattr(self.settings, name):
            setattr(self.settings, name, value)
            self._invalidate_cache()
            return

        # Check if it's in auth settings
        if hasattr(self.auth_settings, name):
            setattr(self.auth_settings, name, value)
            return

        super().__setattr__(name, value)

    @classmethod
    def initialize(cls) -> SettingsService:
        # Check if a string is a valid path or a file name

        settings = Settings()
        if not settings.config_dir:
            msg = "CONFIG_DIR must be set in settings"
            raise ValueError(msg)

        auth_settings = AuthSettings(
            CONFIG_DIR=settings.config_dir,
        )
        return cls(settings, auth_settings)

    def set(self, key, value):
        setattr(self.settings, key, value)
        return self.settings
