"""Deployment adapter registry helpers for deployment router services."""

from __future__ import annotations

from lfx.services.subservice import get_sub_service_registry, register_sub_service

DEPLOYMENT_ADAPTER_NAMESPACE = "deployment.adapters"
DEPLOYMENT_ADAPTER_ENTRY_POINT_GROUP = "lfx.deployment.adapters"
DEPLOYMENT_ADAPTER_CONFIG_SECTION_PATH = ("deployment", "adapters")


def register_deployment_adapter(adapter_key: str, *, override: bool = True):
    """Decorator to register deployment adapter classes."""
    return register_sub_service(DEPLOYMENT_ADAPTER_NAMESPACE, adapter_key, override=override)


def get_deployment_adapter_registry():
    """Return shared deployment adapter registry."""
    return get_sub_service_registry(
        namespace=DEPLOYMENT_ADAPTER_NAMESPACE,
        entry_point_group=DEPLOYMENT_ADAPTER_ENTRY_POINT_GROUP,
        config_section_path=DEPLOYMENT_ADAPTER_CONFIG_SECTION_PATH,
    )
