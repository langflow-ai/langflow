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
    PLUGIN_SERVICE = "plugin_service"
    STORE_SERVICE = "store_service"
    CREDENTIAL_SERVICE = "credential_service"
    STORAGE_SERVICE = "storage_service"
    MONITOR_SERVICE = "monitor_service"
    SOCKET_IO_SERVICE = "socket_io_service"
