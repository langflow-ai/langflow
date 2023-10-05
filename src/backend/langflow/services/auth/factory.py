from langflow.services.factory import ServiceFactory
from langflow.services.auth.service import AuthService


class AuthServiceFactory(ServiceFactory):
    name = "auth_service"

    def __init__(self):
        super().__init__(AuthService)

    def create(self, settings_service):
        return AuthService(settings_service)
