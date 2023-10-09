from langflow.services.base import Service
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsService


class AuthService(Service):
    name = "auth_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
