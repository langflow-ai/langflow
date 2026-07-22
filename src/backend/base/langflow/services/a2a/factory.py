from langflow.services.a2a.service import A2AService
from langflow.services.factory import ServiceFactory


class A2AServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(A2AService)

    def create(self):
        return A2AService()
