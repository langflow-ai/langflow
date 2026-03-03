"""Instance lifecycle tests for generic adapter registry."""

from __future__ import annotations

import pytest
from lfx.services.adapters import registry as adapter_registry_mod
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.schema import AdapterType


class _DeploymentAdapterStub(BaseDeploymentService):
    """Minimal stub subclassing BaseDeploymentService for tests."""

    name = "stub_deployment"

    async def create(self, **kw): ...
    async def list_types(self, **kw): ...
    async def list(self, **kw): ...
    async def get(self, **kw): ...
    async def update(self, **kw): ...
    async def redeploy(self, **kw): ...
    async def duplicate(self, **kw): ...
    async def delete(self, **kw): ...
    async def get_status(self, **kw): ...
    async def create_execution(self, **kw): ...
    async def get_execution(self, **kw): ...
    async def teardown(self): ...


class DummyEntryPointAdapter(_DeploymentAdapterStub):
    pass


class DummyTeardownAdapter(_DeploymentAdapterStub):
    teardown_calls = 0

    async def teardown(self):
        type(self).teardown_calls += 1


@pytest.fixture(autouse=True)
def clean_adapter_globals():
    """Ensure global registry state is isolated per test."""
    adapter_registry_mod._reset_registries()
    yield
    adapter_registry_mod._reset_registries()


def _registry():
    return adapter_registry_mod.get_adapter_registry(
        adapter_type=AdapterType.DEPLOYMENT,
        entry_point_group="lfx.deployment.adapters",
        config_section_path=("deployment", "adapters"),
    )


def test_get_instance_returns_singleton_for_same_key():
    registry = _registry()
    registry.register_class("local", DummyEntryPointAdapter)
    factory_calls = 0

    def factory(adapter_class):
        nonlocal factory_calls
        factory_calls += 1
        return adapter_class()

    first = registry.get_instance("local", factory=factory)
    second = registry.get_instance("local", factory=factory)

    assert first is not None
    assert first is second
    assert factory_calls == 1


def test_get_instance_returns_none_for_unknown_key():
    registry = _registry()

    instance = registry.get_instance("missing", factory=lambda adapter_class: adapter_class())

    assert instance is None


@pytest.mark.asyncio
async def test_teardown_instances_clears_cache_and_recreates():
    DummyTeardownAdapter.teardown_calls = 0
    registry = _registry()
    registry.register_class("local", DummyTeardownAdapter)

    first = registry.get_instance("local", factory=lambda adapter_class: adapter_class())
    assert first is not None

    await registry.teardown_instances()

    second = registry.get_instance("local", factory=lambda adapter_class: adapter_class())
    assert second is not None
    assert second is not first
    assert DummyTeardownAdapter.teardown_calls == 1


@pytest.mark.asyncio
async def test_teardown_all_adapter_registries_clears_instances():
    DummyTeardownAdapter.teardown_calls = 0
    registry = _registry()
    registry.register_class("local", DummyTeardownAdapter)
    registry.get_instance("local", factory=lambda adapter_class: adapter_class())

    await adapter_registry_mod.teardown_all_adapter_registries()

    assert registry.adapter_instances == {}
    assert DummyTeardownAdapter.teardown_calls == 1


def test_get_deployment_adapter_returns_singleton_instance():
    from lfx.services.deps import get_deployment_adapter

    registry = _registry()
    registry.register_class("unit", DummyEntryPointAdapter)

    first = get_deployment_adapter("unit")
    second = get_deployment_adapter("unit")

    assert first is not None
    assert first is second
