from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.base import Settings

# Load .env file if it exists
if not os.environ.get("_LANGFLOW_DOTENV_LOADED"):
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        logger.debug("Loading .env file inside lfx settings service")
        load_dotenv(env_file, override=False)
        os.environ["_LANGFLOW_DOTENV_LOADED"] = "true"

class SettingsService(Service):
    name = "settings_service"

    def __init__(self, settings: Settings, auth_settings: AuthSettings):
        super().__init__()
        self.settings: Settings = settings
        self.auth_settings: AuthSettings = auth_settings

    @classmethod
    def initialize(cls) -> SettingsService:
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

    async def teardown(self):
        pass
