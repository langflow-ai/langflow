from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.deployment_router.service import DeploymentRouterService
from lfx.services.deployment_router.exceptions import (
    DeploymentAccountNotFoundError,
    DeploymentAdapterNotRegisteredError,
    DeploymentRouterError,
)
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


@pytest.mark.anyio
async def test_resolve_adapter_caches_instances(monkeypatch):
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

    async def mock_resolve_adapter_key(*, provider_id, user_id, db):  # noqa: ARG001
        return "watsonx-orchestrate"

    monkeypatch.setattr(service, "_resolve_adapter_key", mock_resolve_adapter_key)
    account_id = uuid4()
    user_id = uuid4()
    db = object()
    first = await service.resolve_adapter(provider_id=account_id, user_id=user_id, db=db)
    second = await service.resolve_adapter(provider_id=account_id, user_id=user_id, db=db)

    assert first is second


@pytest.mark.anyio
async def test_resolve_adapter_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    service = DeploymentRouterService(DummySettingsService())
    account_id = uuid4()
    user_id = uuid4()
    db = object()

    async def mock_resolve_adapter_key(*, provider_id, user_id, db):  # noqa: ARG001
        return "missing-adapter"

    monkeypatch.setattr(service, "_resolve_adapter_key", mock_resolve_adapter_key)

    with pytest.raises(DeploymentAdapterNotRegisteredError, match="No deployment adapter registered"):
        await service.resolve_adapter(provider_id=account_id, user_id=user_id, db=db)


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

    with pytest.raises(DeploymentRouterError, match="unresolved required dependency"):
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


@pytest.mark.anyio
async def test_resolve_adapter_key_requires_owned_provider_account(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    service = DeploymentRouterService(DummySettingsService())

    async def mock_get_provider_account_by_id_for_user(db, *, provider_id, user_id):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        "langflow.services.database.models.deployment_provider_account.crud.get_provider_account_by_id_for_user",
        mock_get_provider_account_by_id_for_user,
    )

    with pytest.raises(DeploymentAccountNotFoundError, match="not found"):
        await service._resolve_adapter_key(provider_id=uuid4(), user_id=uuid4(), db=object())


@pytest.mark.anyio
async def test_resolve_adapter_key_returns_provider_key(monkeypatch):
    monkeypatch.setattr(
        "langflow.services.deployment_router.service.get_deployment_adapter_registry",
        lambda: DummyRegistry(),
    )
    service = DeploymentRouterService(DummySettingsService())

    async def mock_get_provider_account_by_id_for_user(db, *, provider_id, user_id):  # noqa: ARG001
        return SimpleNamespace(provider_key="  watsonx-orchestrate  ")

    monkeypatch.setattr(
        "langflow.services.database.models.deployment_provider_account.crud.get_provider_account_by_id_for_user",
        mock_get_provider_account_by_id_for_user,
    )

    adapter_key = await service._resolve_adapter_key(provider_id=uuid4(), user_id=uuid4(), db=object())
    assert adapter_key == "watsonx-orchestrate"

