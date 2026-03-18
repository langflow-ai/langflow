"""Mapper registry and registration helpers.

Relationship to adapter registries:
- Adapters execute provider operations (create/update/delete/list/status).
- Mappers reshape Langflow API payloads/results into adapter-facing contracts.

Why ``AdapterType`` is used here:
- Mapper lookup must follow the same provider categorization as adapters.
- A mapper is selected by the same pair used by adapters:
  (adapter_type, provider_key).
- Today we only support ``AdapterType.DEPLOYMENT`` mappers, but this
  interface keeps mapper registration aligned with the adapter registry
  model and leaves room for future mapper categories.
"""

from __future__ import annotations

import threading

from lfx.services.adapters.schema import AdapterType

from .base import BaseDeploymentMapper, DeploymentMapperRegistry

_mapper_registry_singleton: DeploymentMapperRegistry | None = None
_mapper_registry_singleton_lock = threading.Lock()


def _get_mapper_registry_singleton() -> DeploymentMapperRegistry:
    """Get or create the deployment mapper registry singleton."""
    global _mapper_registry_singleton  # noqa: PLW0603
    if _mapper_registry_singleton is None:
        with _mapper_registry_singleton_lock:
            if _mapper_registry_singleton is None:
                _mapper_registry_singleton = DeploymentMapperRegistry()
    return _mapper_registry_singleton


def get_mapper_registry(adapter_type: AdapterType) -> DeploymentMapperRegistry:
    """Get mapper registry for a supported adapter type.

    This mirrors adapter-registry routing: the same ``AdapterType`` value
    that selects an adapter category also selects the mapper category.
    """
    if adapter_type is not AdapterType.DEPLOYMENT:
        msg = f"Unsupported mapper adapter type: {adapter_type.value}"
        raise ValueError(msg)
    return _get_mapper_registry_singleton()


def register_mapper(adapter_type: AdapterType, provider_key: str):
    """Decorator that registers a mapper class at import time.

    Decorated mapper classes are recorded in the registry under
    ``(adapter_type, provider_key)`` and instantiated lazily on first lookup.
    """

    def decorator(mapper_class: type[BaseDeploymentMapper]) -> type[BaseDeploymentMapper]:
        registry = get_mapper_registry(adapter_type)
        registry.register(provider_key=provider_key, mapper_class=mapper_class)
        return mapper_class

    return decorator


def get_mapper(adapter_type: AdapterType, provider_key: str | None) -> BaseDeploymentMapper:
    """Resolve mapper by adapter type and provider key with default fallback.

    ``provider_key`` must be the same key used to resolve the concrete adapter
    for the request. This keeps adapter + mapper selection in lockstep.
    """
    registry = get_mapper_registry(adapter_type)
    return registry.get((provider_key or "").strip())
