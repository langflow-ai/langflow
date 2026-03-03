"""Langflow deployment router service implementation."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any

from lfx.services.deployment_router.base import BaseDeploymentRouterService
from lfx.services.deployment_router.context import set_current_deployment_provider_id
from lfx.services.deployment_router.exceptions import (
    DeploymentAccountNotFoundError,
    DeploymentAdapterNotRegisteredError,
    DeploymentRouterError,
)
from lfx.services.deployment_router.registry import get_deployment_adapter_registry
from lfx.services.deps import get_service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.interfaces import DeploymentServiceProtocol
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


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

    async def resolve_adapter(
        self,
        *,
        provider_id: UUID,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentServiceProtocol:
        set_current_deployment_provider_id(provider_id)
        adapter_key = await self._resolve_adapter_key(provider_id=provider_id, user_id=user_id, db=db)
        return self._get_adapter(adapter_key=adapter_key, provider_id=provider_id)

    def list_adapter_keys(self) -> list[str]:
        return self._adapter_registry.list_sub_service_keys()

    async def teardown(self) -> None:
        for adapter in self._adapter_instances.values():
            teardown_result = adapter.teardown()
            if inspect.isawaitable(teardown_result):
                await teardown_result
        self._adapter_instances = {}

    def _get_adapter(self, *, adapter_key: str, provider_id: UUID) -> DeploymentServiceProtocol:
        if adapter_key in self._adapter_instances:
            return self._adapter_instances[adapter_key]

        adapter_class = self._adapter_registry.get_sub_service_class(adapter_key)
        if adapter_class is None:
            msg = (
                f"No deployment adapter registered for provider_id '{provider_id}' "
                f"(resolved adapter key '{adapter_key}')."
            )
            raise DeploymentAdapterNotRegisteredError(message=msg)

        instance = self._instantiate_adapter(adapter_class)
        self._adapter_instances[adapter_key] = instance
        return instance

    async def _resolve_adapter_key(
        self,
        *,
        provider_id: UUID,
        user_id: UUID | str,
        db: AsyncSession,
    ) -> str:
        from langflow.services.database.models.deployment_provider_account.crud import (
            get_provider_account_by_id,
        )

        provider_account = await get_provider_account_by_id(
            db,
            provider_id=provider_id,
            user_id=user_id,
        )
        if provider_account is None:
            msg = f"Deployment provider account '{provider_id}' not found. "
            raise DeploymentAccountNotFoundError(message=msg)

        adapter_key = provider_account.provider_key.strip()
        if not adapter_key:
            msg = f"Deployment provider account '{provider_id}' has no provider_key configured."
            raise DeploymentRouterError(message=msg)
        return adapter_key

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
            raise DeploymentRouterError(message=msg)

        return adapter_class(**dependencies)
