from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from lfx.services.base import Service
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.base import Settings


class SettingsService(Service):
    name = "settings_service"

    def __init__(self, settings: Settings, auth_settings: AuthSettings):
        super().__init__()
        self.settings = settings
        self.auth_settings = auth_settings

    @classmethod
    def load_settings_from_yaml(cls, file_path: str) -> SettingsService:
        # Check if a string is a valid path or a file name
        if "/" not in file_path:
            # Get current path
            current_path = Path(__file__).resolve().parent
            file_path_ = Path(current_path) / file_path
        else:
            file_path_ = Path(file_path)

        with file_path_.open(encoding="utf-8") as f:
            settings_dict = yaml.safe_load(f)
            settings_dict = {k.upper(): v for k, v in settings_dict.items()}

            for key in settings_dict:
                if key not in Settings.model_fields:
                    msg = f"Key {key} not found in settings"
                    raise KeyError(msg)
                logger.debug(f"Loading {len(settings_dict[key])} {key} from {file_path}")

        settings = Settings(**settings_dict)
        if not settings.config_dir:
            msg = "CONFIG_DIR must be set in settings"
            raise ValueError(msg)

        auth_settings = AuthSettings(
            CONFIG_DIR=settings.config_dir,
        )
        return cls(settings, auth_settings)
