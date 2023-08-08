from pathlib import Path
from langflow.services.settings.manager import SettingsManager
from langflow.services.factory import ServiceFactory


class SettingsManagerFactory(ServiceFactory):
    def __init__(self):
        super().__init__(SettingsManager)

    def create(self):
        # Here you would have logic to create and configure a SettingsManager
        langflow_dir = Path(__file__).parent.parent.parent
        return SettingsManager.load_settings_from_yaml(
            str(langflow_dir / "config.yaml")
        )
