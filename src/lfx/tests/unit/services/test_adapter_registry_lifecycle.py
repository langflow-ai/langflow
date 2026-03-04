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

    assert not registry.has_cached_instances()
    assert DummyTeardownAdapter.teardown_calls == 1


def test_get_deployment_adapter_returns_singleton_instance():
    from lfx.services.deps import get_deployment_adapter

    registry = make_deployment_adapter_registry()
    registry.register_class("unit", DummyEntryPointAdapter)

    first = get_deployment_adapter("unit")
    second = get_deployment_adapter("unit")

    assert first is not None
    assert first is second


def test_get_deployment_adapter_returns_none_for_unknown_key():
    from lfx.services.deps import get_deployment_adapter

    registry = make_deployment_adapter_registry()
    registry.register_class("known", DummyEntryPointAdapter)

    result = get_deployment_adapter("nonexistent")

    assert result is None


def test_register_class_evicts_stale_cached_instance():
    """Re-registering a key with a different class evicts the cached instance."""

    class AdapterA(DeploymentAdapterStub):
        pass

    class AdapterB(DeploymentAdapterStub):
        pass

    registry = make_deployment_adapter_registry()
    registry.register_class("local", AdapterA)
    first = registry.get_instance("local", factory=lambda cls: cls())
    assert isinstance(first, AdapterA)

    registry.register_class("local", AdapterB, override=True)
    second = registry.get_instance("local", factory=lambda cls: cls())
    assert isinstance(second, AdapterB)
    assert second is not first


def test_factory_exception_does_not_poison_cache():
    """A failing factory should not prevent subsequent successful creation."""
    registry = make_deployment_adapter_registry()
    registry.register_class("local", DummyEntryPointAdapter)
    call_count = 0

    def failing_then_succeeding_factory(adapter_class):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            msg = "factory failed"
            raise RuntimeError(msg)
        return adapter_class()

    with pytest.raises(RuntimeError, match="factory failed"):
        registry.get_instance("local", factory=failing_then_succeeding_factory)

    instance = registry.get_instance("local", factory=failing_then_succeeding_factory)
    assert instance is not None
    assert isinstance(instance, DummyEntryPointAdapter)


@pytest.mark.asyncio
async def test_teardown_exception_does_not_prevent_other_teardowns():
    """If one adapter's teardown raises, other adapters still get torn down."""

    class FailingTeardownAdapter(DeploymentAdapterStub):
        async def teardown(self):
            msg = "boom"
            raise RuntimeError(msg)

    class TrackingTeardownAdapter(DeploymentAdapterStub):
        teardown_called = False

        async def teardown(self):
            type(self).teardown_called = True

    TrackingTeardownAdapter.teardown_called = False
    registry = make_deployment_adapter_registry()
    registry.register_class("failing", FailingTeardownAdapter)
    registry.register_class("tracking", TrackingTeardownAdapter)
    registry.get_instance("failing", factory=lambda cls: cls())
    registry.get_instance("tracking", factory=lambda cls: cls())

    await registry.teardown_instances()

    assert TrackingTeardownAdapter.teardown_called
    assert not registry.has_cached_instances()


@pytest.mark.asyncio
async def test_sync_teardown_is_called():
    """Adapters with a synchronous teardown() should still be called."""
    calls: list[str] = []

    class SyncTeardownAdapter(DeploymentAdapterStub):
        def teardown(self):
            calls.append("torn_down")

    registry = make_deployment_adapter_registry()
    registry.register_class("sync", SyncTeardownAdapter)
    registry.get_instance("sync", factory=lambda cls: cls())

    await registry.teardown_instances()

    assert calls == ["torn_down"]
    assert not registry.has_cached_instances()


@pytest.mark.asyncio
async def test_adapter_without_teardown_does_not_raise():
    """Adapters with no teardown method should be cleaned up without error."""

    class NoTeardownAdapter(DeploymentAdapterStub):
        teardown = None  # type: ignore[assignment]

    registry = make_deployment_adapter_registry()
    registry.register_class("plain", NoTeardownAdapter)
    registry.get_instance("plain", factory=lambda cls: cls())

    await registry.teardown_instances()

    assert not registry.has_cached_instances()
