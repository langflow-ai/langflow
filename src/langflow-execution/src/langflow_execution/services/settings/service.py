from __future__ import annotations
from pydantic_settings import BaseSettings

from langflow_execution.services.service import Service


class AuthSettings(BaseSettings):
    AUTO_LOGIN: bool = False


class Settings(BaseSettings):
    telemetry_base_url: str = "https://langflow.gateway.scarf.sh"
    prometheus_enabled: bool = False
    do_not_track: bool = False
    cache_type: str = "InMemoryCache"
    backend_only: bool = False
    fallback_to_env_vars: bool = False

class SettingsService(Service):
    name = "settings_service"

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.auth_settings = AuthSettings()
        self.set_ready()

    async def teardown(self):
        pass  # No teardown logic needed for settings
