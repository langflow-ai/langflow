from enum import Enum


class ServiceType(str, Enum):
    """
    Enum for the different types of services that can be
    registered with the service manager.
    """

    AUTH_MANAGER = "auth_service"
    CACHE_MANAGER = "cache_service"
    SETTINGS_MANAGER = "settings_service"
    DATABASE_MANAGER = "database_service"
    CHAT_MANAGER = "chat_service"
    SESSION_MANAGER = "session_service"
    TASK_MANAGER = "task_service"
