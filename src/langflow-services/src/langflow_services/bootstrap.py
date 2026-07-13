"""Register concrete service factories and built-in adapters."""

from __future__ import annotations

from importlib import import_module

from lfx.log.logger import logger
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from lfx.services.settings.feature_flags import FEATURE_FLAGS


def register_all_service_factories() -> None:
    """Register concrete Langflow factories/classes on the LFX service manager."""
    service_manager = get_service_manager()

    from lfx.services.executor import factory as executor_factory
    from lfx.services.mcp_composer import factory as mcp_composer_factory
    from lfx.services.settings import factory as settings_factory

    from langflow_services.auth import factory as auth_factory
    from langflow_services.auth.service import AuthService
    from langflow_services.authorization import factory as authorization_factory
    from langflow_services.authorization.service import LangflowAuthorizationService
    from langflow_services.cache import factory as cache_factory
    from langflow_services.chat import factory as chat_factory
    from langflow_services.database import factory as database_factory
    from langflow_services.job_queue import factory as job_queue_factory
    from langflow_services.session import factory as session_factory
    from langflow_services.shared_component_cache import factory as shared_component_cache_factory
    from langflow_services.state import factory as state_factory
    from langflow_services.storage import factory as storage_factory
    from langflow_services.store import factory as store_factory
    from langflow_services.task import factory as task_factory
    from langflow_services.telemetry import factory as telemetry_factory
    from langflow_services.telemetry_writer import factory as telemetry_writer_factory
    from langflow_services.tracing import factory as tracing_factory
    from langflow_services.transaction import factory as transaction_factory
    from langflow_services.variable import factory as variable_factory

    service_manager.register_factory(settings_factory.SettingsServiceFactory())
    service_manager.register_factory(cache_factory.CacheServiceFactory())
    service_manager.register_factory(chat_factory.ChatServiceFactory())
    service_manager.register_factory(database_factory.DatabaseServiceFactory())
    service_manager.register_factory(session_factory.SessionServiceFactory())
    service_manager.register_factory(storage_factory.StorageServiceFactory())
    service_manager.register_factory(variable_factory.VariableServiceFactory())
    service_manager.register_factory(telemetry_factory.TelemetryServiceFactory())
    service_manager.register_factory(tracing_factory.TracingServiceFactory())
    service_manager.register_factory(transaction_factory.TransactionServiceFactory())
    service_manager.register_factory(telemetry_writer_factory.TelemetryWriterServiceFactory())
    service_manager.register_factory(state_factory.StateServiceFactory())
    service_manager.register_factory(job_queue_factory.JobQueueServiceFactory())
    service_manager.register_factory(task_factory.TaskServiceFactory())
    service_manager.register_factory(store_factory.StoreServiceFactory())
    service_manager.register_factory(shared_component_cache_factory.SharedComponentCacheServiceFactory())
    # jobs / flow_events / memory_base stay lazy via langflow.services.deps getters
    # so optional backends (e.g. chromadb for MemoryBase) are not imported at startup.

    service_manager.register_service_class(ServiceType.AUTH_SERVICE, AuthService, override=True)
    service_manager.register_factory(auth_factory.AuthServiceFactory())
    service_manager.register_service_class(
        ServiceType.AUTHORIZATION_SERVICE, LangflowAuthorizationService, override=True
    )
    service_manager.register_factory(authorization_factory.AuthorizationServiceFactory())
    service_manager.register_factory(mcp_composer_factory.MCPComposerServiceFactory())
    service_manager.register_factory(executor_factory.ExecutorServiceFactory())
    service_manager.set_factory_registered()


def register_builtin_adapters() -> None:
    """Import built-in adapter registration modules."""
    if not FEATURE_FLAGS.wxo_deployments:
        logger.debug("Skipping deployment adapter registration: wxo_deployments feature flag disabled")
        return

    try:
        import_module("langflow_services.adapters.deployment.watsonx_orchestrate.register")
    except ModuleNotFoundError as exc:
        logger.info("Skipping Watsonx Orchestrate adapter registration: %s", exc)
