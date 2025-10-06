from dotenv import find_dotenv
from flask.cli import load_dotenv
from typing_extensions import override

from langflow.logging.logger import logger
from langflow.services.factory import ServiceFactory
from langflow.services.settings.service import SettingsService


class SettingsServiceFactory(ServiceFactory):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        super().__init__(SettingsService)

    def _load_env_vars(self) -> bool:
        env_file = find_dotenv()
        if env_file:
            logger.debug(f"Loading environment variables from {env_file}")
            return load_dotenv(env_file)
        return False

    @override
    def create(self):
        # Here you would have logic to create and configure a SettingsService
        # Try to load env file if not already loaded
        self._load_env_vars()
        return SettingsService.initialize()
