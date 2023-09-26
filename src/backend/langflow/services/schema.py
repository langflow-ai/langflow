from enum import Enum


class ServiceType(str, Enum):
    """
    Enum for the different types of services that can be
    registered with the service manager.
    """

    AUTH_SERVICE = "auth_service"
    CACHE_SERVICE = "cache_service"
    SETTINGS_SERVICE = "settings_service"
    DATABASE_SERVICE = "database_service"
    CHAT_SERVICE = "chat_service"
    SESSION_SERVICE = "session_service"
    TASK_SERVICE = "task_service"
