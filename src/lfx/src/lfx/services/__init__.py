"""LFX services module - pluggable service architecture for dependency injection."""

from .interfaces import (
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
    "register_service",
]
