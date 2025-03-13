from langflow.services.discord.service import DiscordService
from langflow.services.factory import ServiceFactory


class DiscordServiceFactory(ServiceFactory):
    """Factory for creating Discord service instances."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__(DiscordService)

    def create(self) -> DiscordService:
        """Create a new Discord service instance."""
        return DiscordService()
