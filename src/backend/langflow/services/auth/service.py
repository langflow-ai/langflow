from fastapi import Request
from langflow.services.base import Service
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsManager


class AuthManager(Service):
    name = "auth_manager"

    def __init__(self, settings_manager: "SettingsManager"):
        self.settings_manager = settings_manager

    # We need to define a function that can be passed to the Depends() function.
    # This function will be called by FastAPI to run oauth2_scheme
    def run_oauth2_scheme(self, request: Request):
        return self.settings_manager.auth_settings.oauth2_scheme(request=request)
