"""Langflow deployment router service implementation."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

from lfx.services.deployment.exceptions import DeploymentError
from lfx.services.deployment_router.base import BaseDeploymentRouterService
from lfx.services.deployment_router.registry import get_deployment_adapter_registry
from lfx.services.deps import get_service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.deployment.schema import DeploymentProviderId
    from lfx.services.interfaces import DeploymentServiceProtocol
    from lfx.services.settings.service import SettingsService


class DeploymentRouterService(BaseDeploymentRouterService):
    """Resolves provider routing IDs into deployment adapter instances."""

    name = ServiceType.DEPLOYMENT_ROUTER_SERVICE.value
    builtin_adapter_modules = ("langflow.services.deployment.watsonx_orchestrate",)

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self._adapter_instances: dict[str, DeploymentServiceProtocol] = {}
        self._adapter_registry = get_deployment_adapter_registry()
        config_dir = getattr(settings_service.settings, "config_dir", None)
        self._preload_builtin_adapter_modules()
        self._adapter_registry.discover_sub_services(config_dir=config_dir)
        self.set_ready()

    def resolve_adapter(
        self,
        *,
        provider_id: DeploymentProviderId,
    ) -> DeploymentServiceProtocol:
        return self._get_adapter(provider_id)

    def list_adapter_keys(self) -> list[str]:
        return self._adapter_registry.list_sub_service_keys()

    async def teardown(self) -> None:
        for adapter in self._adapter_instances.values():
            teardown_result = adapter.teardown()
            if inspect.isawaitable(teardown_result):
                await teardown_result
        self._adapter_instances = {}

    def _get_adapter(self, provider_id: DeploymentProviderId) -> DeploymentServiceProtocol:
        adapter_key = self._resolve_adapter_key(provider_id)
        if adapter_key in self._adapter_instances:
            return self._adapter_instances[adapter_key]

        adapter_class = self._adapter_registry.get_sub_service_class(adapter_key)
        if adapter_class is None:
            msg = (
                f"No deployment adapter registered for provider_id '{provider_id}' "
                f"(resolved adapter key '{adapter_key}')."
            )
            raise DeploymentError(message=msg)

        instance = self._instantiate_adapter(adapter_class)
        self._adapter_instances[adapter_key] = instance
        return instance

    def _resolve_adapter_key(self, provider_id: DeploymentProviderId) -> str:
        # Placeholder strategy for initial API flow: provider_id maps directly to
        # deployment adapter key. A provider table lookup can be introduced later.
        return str(provider_id).strip()

    def _preload_builtin_adapter_modules(self) -> None:
        """Import built-in adapter modules so decorator registration is deterministic."""
        for module_path in self.builtin_adapter_modules:
            importlib.import_module(module_path)

    def _instantiate_adapter(self, adapter_class: type[DeploymentServiceProtocol]) -> DeploymentServiceProtocol:
        signature = inspect.signature(adapter_class.__init__)
        dependencies = {}

        for name, parameter in signature.parameters.items():
            if name == "self":
                continue

            service = None
            try:
                service_type = ServiceType(name)
                service = get_service(service_type)
            except ValueError:
                service = None

            if service is not None:
                dependencies[name] = service
                continue

            if parameter.default is not inspect.Parameter.empty:
                continue

            msg = f"Failed to instantiate adapter '{adapter_class.__name__}': unresolved required dependency '{name}'."
            raise DeploymentError(message=msg)

        return adapter_class(**dependencies)
