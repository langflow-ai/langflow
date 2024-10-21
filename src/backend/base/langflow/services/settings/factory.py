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

    def create(self):
        # Here you would have logic to create and configure a SettingsService

        return SettingsService.initialize()
