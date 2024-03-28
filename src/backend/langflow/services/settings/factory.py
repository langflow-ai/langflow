import os
from pathlib import Path
from langflow.services.settings.service import SettingsService
from langflow.services.factory import ServiceFactory

component_config_path = os.getenv("COMPONENT_CONFIG_PATH", str(Path(__file__).parent / "component_config.yaml"))


class SettingsServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(SettingsService)

    def create(self):
        # Here you would have logic to create and configure a SettingsService
        return SettingsService.load_settings_from_yaml(component_config_path)
