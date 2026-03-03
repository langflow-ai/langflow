"""LFX services module - pluggable service architecture for dependency injection."""

from .adapter_registry import (
    AdapterRegistry,
    AdapterRegistryConflictError,
    get_adapter_registry,
    register_adapter,
    teardown_all_adapter_registries,
)
from .deps import get_deployment_adapter, get_deployment_registry
from .interfaces import (
    AuthServiceProtocol,
    CacheServiceProtocol,
    ChatServiceProtocol,
    DatabaseServiceProtocol,
    SettingsServiceProtocol,
    StorageServiceProtocol,
    TracingServiceProtocol,
    VariableServiceProtocol,
)
from .manager import ServiceManager
from .mcp_composer import MCPComposerService, MCPComposerServiceFactory
from .registry import register_service
from .session import NoopSession

__all__ = [
    "AdapterRegistry",
    "AdapterRegistryConflictError",
    "AuthServiceProtocol",
    "CacheServiceProtocol",
    "ChatServiceProtocol",
    "DatabaseServiceProtocol",
    "MCPComposerService",
    "MCPComposerServiceFactory",
    "NoopSession",
    "ServiceManager",
    "SettingsServiceProtocol",
    "StorageServiceProtocol",
    "TracingServiceProtocol",
    "VariableServiceProtocol",
    "get_adapter_registry",
    "get_deployment_adapter",
    "get_deployment_registry",
    "register_adapter",
    "register_service",
    "teardown_all_adapter_registries",
]
