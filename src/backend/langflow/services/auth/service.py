from langflow.services.base import Service


class AuthManager(Service):
    name = "auth_manager"

    def __init__(self, settings_manager):
        self.settings_manager = settings_manager

    # We need to define a function that can be passed to the Depends() function.
    # This function will be called by FastAPI to run oauth2_scheme
    def run_oauth2_scheme(self, *args, **kwargs):
        return self.settings_manager.auth_settings.oauth2_scheme(*args, **kwargs)
