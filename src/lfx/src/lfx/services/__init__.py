"""LFX services module - pluggable service architecture for dependency injection."""

from .adapters.registry import register_adapter, teardown_all_adapter_registries
from .deps import get_deployment_adapter
from .interfaces import (
    AuthServiceProtocol,
    CacheServiceProtocol,
    ChatServiceProtocol,
    DatabaseServiceProtocol,
    DeploymentServiceProtocol,
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
    "AuthServiceProtocol",
    "CacheServiceProtocol",
    "ChatServiceProtocol",
    "DatabaseServiceProtocol",
    "DeploymentServiceProtocol",
    "MCPComposerService",
    "MCPComposerServiceFactory",
    "NoopSession",
    "ServiceManager",
    "SettingsServiceProtocol",
    "StorageServiceProtocol",
    "TracingServiceProtocol",
    "VariableServiceProtocol",
    "get_deployment_adapter",
    "register_adapter",
    "register_service",
    "teardown_all_adapter_registries",
]
