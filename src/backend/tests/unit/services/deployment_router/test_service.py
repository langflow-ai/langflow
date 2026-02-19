from __future__ import annotations

from types import SimpleNamespace

import pytest

from langflow.services.deployment_router.service import DeploymentRouterService
from lfx.services.deployment.exceptions import DeploymentError
from lfx.services.schema import ServiceType


class DummyRegistry:
    def __init__(self):
        self.discover_config_dir = None
        self.sub_services = {}

    def discover_sub_services(self, *, config_dir=None):
        self.discover_config_dir = config_dir

    def get_sub_service_class(self, key: str):
        return self.sub_services.get(key)

    def list_sub_service_keys(self):
        return sorted(self.sub_services.keys())


class DummySettingsService:
    def __init__(self, config_dir: str = "/tmp/config"):
        self.settings = SimpleNamespace(config_dir=config_dir)


class AdapterWithSyncTeardown:
    teardown_called = 0

    def teardown(self):
        AdapterWithSyncTeardown.teardown_called += 1


class AdapterWithAsyncTeardown:
    teardown_called = 0

    async def teardown(self):
        AdapterWithAsyncTeardown.teardown_called += 1


def test_initializes_registry_and_preloads_builtin_modules(monkeypatch):
    registry = DummyRegistry()
    imported_modules = []

    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.importlib.import_module",
        lambda module: imported_modules.append(module),
    )

    service = DeploymentRouterService(DummySettingsService("/tmp/my-config"))

    assert service.ready
    assert registry.discover_config_dir == "/tmp/my-config"
    assert imported_modules == ["langflow.services.deployment.watsonx_orchestrate"]


def test_resolve_adapter_caches_instances(monkeypatch):
    registry = DummyRegistry()
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: registry,
    )

    class DummyAdapter:
        def __init__(self):
            pass

        def teardown(self):
            return None

    registry.sub_services["watsonx-orchestrate"] = DummyAdapter
    service = DeploymentRouterService(DummySettingsService())

    first = service.resolve_adapter(provider_id="watsonx-orchestrate")
    second = service.resolve_adapter(provider_id="  watsonx-orchestrate  ")

    assert first is second


def test_resolve_adapter_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    service = DeploymentRouterService(DummySettingsService())

    with pytest.raises(DeploymentError, match="No deployment adapter registered"):
        service.resolve_adapter(provider_id="missing-adapter")


def test_list_adapter_keys_delegates_to_registry(monkeypatch):
    registry = DummyRegistry()
    registry.sub_services["b"] = object
    registry.sub_services["a"] = object
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: registry,
    )

    service = DeploymentRouterService(DummySettingsService())

    assert service.list_adapter_keys() == ["a", "b"]


def test_instantiate_adapter_resolves_named_service_dependency(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    settings_service = DummySettingsService()
    service = DeploymentRouterService(settings_service)

    class Adapter:
        def __init__(self, settings_service):
            self.settings_service = settings_service

        def teardown(self):
            return None

    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_service",
        lambda service_type: settings_service if service_type == ServiceType.SETTINGS_SERVICE else None,
    )

    instance = service._instantiate_adapter(Adapter)

    assert instance.settings_service is settings_service


def test_instantiate_adapter_raises_for_unresolved_required_dependency(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    service = DeploymentRouterService(DummySettingsService())

    class Adapter:
        def __init__(self, required_dependency):
            self.required_dependency = required_dependency

        def teardown(self):
            return None

    with pytest.raises(DeploymentError, match="unresolved required dependency"):
        service._instantiate_adapter(Adapter)


@pytest.mark.anyio
async def test_teardown_handles_sync_and_async_adapter_teardown(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    service = DeploymentRouterService(DummySettingsService())
    AdapterWithSyncTeardown.teardown_called = 0
    AdapterWithAsyncTeardown.teardown_called = 0
    service._adapter_instances = {
        "sync": AdapterWithSyncTeardown(),
        "async": AdapterWithAsyncTeardown(),
    }

    await service.teardown()

    assert AdapterWithSyncTeardown.teardown_called == 1
    assert AdapterWithAsyncTeardown.teardown_called == 1
    assert service._adapter_instances == {}

