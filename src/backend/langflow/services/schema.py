from enum import Enum


class ServiceType(str, Enum):
    """
    Enum for the different types of services that can be
    registered with the service manager.
    """

    CACHE_MANAGER = "cache_manager"
    SETTINGS_MANAGER = "settings_manager"
    DATABASE_MANAGER = "database_manager"
    CHAT_MANAGER = "chat_manager"
