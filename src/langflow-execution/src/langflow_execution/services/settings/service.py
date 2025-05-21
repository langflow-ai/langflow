from __future__ import annotations

import os
from pathlib import Path

from loguru import logger
from pydantic import field_validator
from pydantic_settings import BaseSettings

from langflow_execution.services.service import Service

BASE_COMPONENTS_PATH = str(Path(__file__).parent.parent / "components")


class AuthSettings(BaseSettings):
    AUTO_LOGIN: bool = False


class Settings(BaseSettings):
    telemetry_base_url: str = "https://langflow.gateway.scarf.sh"
    prometheus_enabled: bool = False
    do_not_track: bool = False
    cache_type: str = "InMemoryCache"
    backend_only: bool = False
    fallback_to_env_vars: bool = False
    components_path: list[str] = []

    @field_validator("components_path", mode="before")
    @classmethod
    def set_components_path(cls, value):
        if os.getenv("LANGFLOW_COMPONENTS_PATH"):
            logger.debug("Adding LANGFLOW_COMPONENTS_PATH to components_path")
            langflow_component_path = os.getenv("LANGFLOW_COMPONENTS_PATH")
            if Path(langflow_component_path).exists() and langflow_component_path not in value:
                if isinstance(langflow_component_path, list):
                    for path in langflow_component_path:
                        if path not in value:
                            value.append(path)
                    logger.debug(f"Extending {langflow_component_path} to components_path")
                elif langflow_component_path not in value:
                    value.append(langflow_component_path)
                    logger.debug(f"Appending {langflow_component_path} to components_path")

        if not value:
            value = [BASE_COMPONENTS_PATH]
            logger.debug("Setting default components path to components_path")
        elif BASE_COMPONENTS_PATH not in value:
            value.append(BASE_COMPONENTS_PATH)
            logger.debug("Adding default components path to components_path")

        logger.debug(f"Components path: {value}")
        return value


class SettingsService(Service):
    name = "settings_service"

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.auth_settings = AuthSettings()
        self.set_ready()

    async def teardown(self):
        pass  # No teardown logic needed for settings
