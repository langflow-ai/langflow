from langflow.services.chat.manager import ChatManager
from langflow.services.factory import ServiceFactory


class ChatManagerFactory(ServiceFactory):
    def __init__(self):
        super().__init__(ChatManager)

    def create(self, settings_service):
        # Here you would have logic to create and configure a ChatManager
        return ChatManager()
