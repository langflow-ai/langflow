from langflow.services.base import Service
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsManager


class AuthManager(Service):
    name = "auth_manager"

    def __init__(self, settings_manager: "SettingsManager"):
        self.settings_manager = settings_manager
