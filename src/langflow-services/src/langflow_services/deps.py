"""Service getters used by concrete implementations.

Re-exports portable LFX session helpers and restores the factory-default
resolution semantics that ``langflow.services.deps`` historically provided.

Unlike LFX ``get_service``, failures propagate (they are not swallowed as
``None``).
"""

from __future__ import annotations

from lfx.services.deps import (  # noqa: F401
    injectable_session_scope,
    session_scope,
    session_scope_readonly,
)
from lfx.services.schema import ServiceType


def get_service(service_type: ServiceType, default=None):
    """Resolve a service, raising on factory/construction failure."""
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()

    if not service_manager.are_factories_registered():
        service_manager.register_factories(service_manager.get_factories())

    if ServiceType.SETTINGS_SERVICE not in service_manager.factories:
        from lfx.services.settings.factory import SettingsServiceFactory

        service_manager.register_factory(service_factory=SettingsServiceFactory())

    return service_manager.get(service_type, default)


def get_auth_service():
    from langflow_services.auth.factory import AuthServiceFactory

    return get_service(ServiceType.AUTH_SERVICE, AuthServiceFactory())


def get_settings_service():
    from lfx.services.settings.factory import SettingsServiceFactory

    return get_service(ServiceType.SETTINGS_SERVICE, SettingsServiceFactory())


def get_db_service():
    from langflow_services.database.factory import DatabaseServiceFactory

    return get_service(ServiceType.DATABASE_SERVICE, DatabaseServiceFactory())


def get_storage_service():
    from langflow_services.storage.factory import StorageServiceFactory

    return get_service(ServiceType.STORAGE_SERVICE, StorageServiceFactory())


def get_variable_service():
    from langflow_services.variable.factory import VariableServiceFactory

    return get_service(ServiceType.VARIABLE_SERVICE, VariableServiceFactory())


def get_cache_service():
    from langflow_services.cache.factory import CacheServiceFactory

    return get_service(ServiceType.CACHE_SERVICE, CacheServiceFactory())


def get_queue_service():
    from langflow_services.job_queue.factory import JobQueueServiceFactory

    return get_service(ServiceType.JOB_QUEUE_SERVICE, JobQueueServiceFactory())


def get_task_service():
    from langflow_services.task.factory import TaskServiceFactory

    return get_service(ServiceType.TASK_SERVICE, TaskServiceFactory())


def get_job_service():
    from langflow_services.jobs.factory import JobServiceFactory

    return get_service(ServiceType.JOB_SERVICE, JobServiceFactory())


def get_telemetry_writer_service():
    from langflow_services.telemetry_writer.factory import TelemetryWriterServiceFactory

    return get_service(ServiceType.TELEMETRY_WRITER_SERVICE, TelemetryWriterServiceFactory())


def get_telemetry_service():
    from langflow_services.telemetry.factory import TelemetryServiceFactory

    return get_service(ServiceType.TELEMETRY_SERVICE, TelemetryServiceFactory())
