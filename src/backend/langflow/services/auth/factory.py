from langflow.services.factory import ServiceFactory
from langflow.services.auth.service import AuthManager


class AuthManagerFactory(ServiceFactory):
    name = "auth_manager"

    def __init__(self):
        super().__init__(AuthManager)

    def create(self, settings_manager):
        return AuthManager(settings_manager)
