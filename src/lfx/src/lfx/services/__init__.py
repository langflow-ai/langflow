"""LFX services module - pluggable service architecture for dependency injection."""

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
from .subservice import SubServiceRegistry, get_sub_service_registry, register_sub_service

__all__ = [
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
    "SubServiceRegistry",
    "TracingServiceProtocol",
    "VariableServiceProtocol",
    "get_sub_service_registry",
    "register_service",
    "register_sub_service",
]
