"""Instance lifecycle tests for generic adapter registry."""

from __future__ import annotations

import pytest
from lfx.services.adapters import registry as adapter_registry_mod

from tests.unit.services.adapter_test_helpers import DeploymentAdapterStub, make_deployment_adapter_registry


class DummyEntryPointAdapter(DeploymentAdapterStub):
    pass


class DummyTeardownAdapter(DeploymentAdapterStub):
    teardown_calls = 0

    async def teardown(self):
        type(self).teardown_calls += 1


pytestmark = pytest.mark.usefixtures("clean_adapter_globals")


def test_get_instance_returns_singleton_for_same_key():
    registry = make_deployment_adapter_registry()
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
    registry = make_deployment_adapter_registry()

    instance = registry.get_instance("missing", factory=lambda adapter_class: adapter_class())

    assert instance is None


@pytest.mark.asyncio
async def test_teardown_instances_clears_cache_and_recreates():
    DummyTeardownAdapter.teardown_calls = 0
    registry = make_deployment_adapter_registry()
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
    registry = make_deployment_adapter_registry()
    registry.register_class("local", DummyTeardownAdapter)
    registry.get_instance("local", factory=lambda adapter_class: adapter_class())

    await adapter_registry_mod.teardown_all_adapter_registries()

    assert registry.adapter_instances == {}
    assert DummyTeardownAdapter.teardown_calls == 1


def test_get_deployment_adapter_returns_singleton_instance():
    from lfx.services.deps import get_deployment_adapter

    registry = make_deployment_adapter_registry()
    registry.register_class("unit", DummyEntryPointAdapter)

    first = get_deployment_adapter("unit")
    second = get_deployment_adapter("unit")

    assert first is not None
    assert first is second
