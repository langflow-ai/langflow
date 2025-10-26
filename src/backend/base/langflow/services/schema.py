from enum import Enum


class ServiceType(str, Enum):
    """Enum for the different types of services that can be registered with the service manager."""

    AUTH_SERVICE = "auth_service"
    CACHE_SERVICE = "cache_service"
    SHARED_COMPONENT_CACHE_SERVICE = "shared_component_cache_service"
    SETTINGS_SERVICE = "settings_service"
    DATABASE_SERVICE = "database_service"
    CHAT_SERVICE = "chat_service"
    SESSION_SERVICE = "session_service"
    TASK_SERVICE = "task_service"
    STORE_SERVICE = "store_service"
    VARIABLE_SERVICE = "variable_service"
    STORAGE_SERVICE = "storage_service"
    # SOCKETIO_SERVICE = "socket_service"
    STATE_SERVICE = "state_service"
    TRACING_SERVICE = "tracing_service"
    TELEMETRY_SERVICE = "telemetry_service"
    JOB_QUEUE_SERVICE = "job_queue_service"
    MCP_COMPOSER_SERVICE = "mcp_composer_service"
    MODELHUB_SERVICE = "modelhub_service"
    KNOWLEDGE_SERVICE = "knowledge_service"
    FLEXSTORE_SERVICE = "flexstore_service"
    PROMPT_SERVICE = "prompt_service"
    # Genesis Services
    PA_LOOKUP_SERVICE = "pa_lookup_service"
    CLAIM_AUTH_HISTORY_SERVICE = "claim_auth_history_service"
    ENCODER_PRO_SERVICE = "encoder_pro_service"
