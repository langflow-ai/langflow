"""Service schema definitions for lfx package."""

from __future__ import annotations

from enum import Enum


class ServiceType(str, Enum):
    AUTH_SERVICE = "auth_service"
    AUTHORIZATION_SERVICE = "authorization_service"
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
    SHARED_COMPONENT_CACHE_SERVICE = "shared_component_cache_service"
    MCP_COMPOSER_SERVICE = "mcp_composer_service"
    TRANSACTION_SERVICE = "transaction_service"
    FLOW_EVENTS_SERVICE = "flow_events_service"
    TELEMETRY_WRITER_SERVICE = "telemetry_writer_service"
    EXTENSION_EVENTS_SERVICE = "extension_events_service"
