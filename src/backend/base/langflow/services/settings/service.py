import os

import yaml
from loguru import logger

from langflow.services.base import Service
from langflow.services.settings.auth import AuthSettings
from langflow.services.settings.base import Settings


class SettingsService(Service):
    name = "settings_service"

    def __init__(self, settings: Settings, auth_settings: AuthSettings):
        super().__init__()
        self.settings: Settings = settings
        self.auth_settings: AuthSettings = auth_settings

    @classmethod
    def load_settings_from_yaml(cls, file_path: str) -> "SettingsService":
        # Check if a string is a valid path or a file name
        if "/" not in file_path:
            # Get current path
            current_path = os.path.dirname(os.path.abspath(__file__))

            file_path = os.path.join(current_path, file_path)

        with open(file_path, "r") as f:
            settings_dict = yaml.safe_load(f)

            for key in settings_dict:
                if key not in Settings.model_fields.keys():
                    logger.warning(f"Key {key} not found in settings")
                logger.debug(f"Loading {len(settings_dict[key])} {key} from {file_path}")

        settings = Settings(**settings_dict)
        if not settings.config_dir:
            raise ValueError("CONFIG_DIR must be set in settings")

        auth_settings = AuthSettings(
            CONFIG_DIR=settings.config_dir,
        )
        return cls(settings, auth_settings)

    def set(self, key, value):
        setattr(self.settings, key, value)
        return self.settings
