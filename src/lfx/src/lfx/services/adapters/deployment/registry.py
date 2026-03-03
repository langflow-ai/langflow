"""Typed deployment adapter registry helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.deps import get_deployment_adapter, get_deployment_registry

if TYPE_CHECKING:
    from lfx.services.interfaces import DeploymentServiceProtocol


def get_registry():
    """Return the deployment adapter registry singleton."""
    return get_deployment_registry()


def resolve_adapter(
    adapter_key: str,
) -> DeploymentServiceProtocol | None:
    """Resolve a singleton deployment adapter instance by key."""
    return get_deployment_adapter(adapter_key)
