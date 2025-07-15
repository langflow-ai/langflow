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

    # ---------------------------------------------------------------------
    # Convenience accessors for grouped settings
    # ---------------------------------------------------------------------
    @property
    def database(self) -> DatabaseSettings:
        """Return database-related settings."""
        return DatabaseSettings(**self.settings.model_dump())

    @property
    def redis(self) -> RedisSettings:
        """Return redis-related settings."""
        return RedisSettings(**self.settings.model_dump())

    @property
    def server(self) -> ServerSettings:
        """Return web-server settings."""
        return ServerSettings(**self.settings.model_dump())

    @property
    def telemetry(self) -> TelemetrySettings:
        """Return telemetry settings."""
        return TelemetrySettings(**self.settings.model_dump())

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
