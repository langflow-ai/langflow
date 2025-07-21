"""Service schema definitions for lfx package."""

from enum import Enum


class ServiceType(Enum):
    DATABASE_SERVICE = "database_service"
    STORAGE_SERVICE = "storage_service"
    SETTINGS_SERVICE = "settings_service"
    VARIABLE_SERVICE = "variable_service"
    CACHE_SERVICE = "cache_service"
    TELEMETRY_SERVICE = "telemetry_service"
    TRACING_SERVICE = "tracing_service"
    STATE_SERVICE = "state_service"
    SESSION_SERVICE = "session_service"
    CHAT_SERVICE = "chat_service"
    TASK_SERVICE = "task_service"
    STORE_SERVICE = "store_service"
    JOB_QUEUE_SERVICE = "job_queue_service"
