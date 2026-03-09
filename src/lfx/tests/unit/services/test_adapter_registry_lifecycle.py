"""Instance lifecycle tests for generic adapter registry."""

from __future__ import annotations

import pytest
from lfx.services.adapters import registry as adapter_registry_mod

from tests.unit.services.adapter_test_helpers import DeploymentAdapterStub, make_deployment_adapter_registry


class DummyEntryPointAdapter(DeploymentAdapterStub):
    pass


class DummyTeardownAdapter(DeploymentAdapterStub):
    """Adapter stub that tracks teardown calls via an external list.

    Each test that uses this must provide its own ``teardown_log`` list
    to avoid shared mutable class-level state across parallel tests.
    """

    def __init__(self, *, teardown_log: list[str] | None = None):
        self._teardown_log = teardown_log if teardown_log is not None else []

    async def teardown(self):
        self._teardown_log.append("teardown")


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
    teardown_log: list[str] = []
    registry = make_deployment_adapter_registry()
    registry.register_class("local", DummyTeardownAdapter)

    first = registry.get_instance("local", factory=lambda cls: cls(teardown_log=teardown_log))
    assert first is not None

    await registry.teardown_instances()

    second = registry.get_instance("local", factory=lambda cls: cls(teardown_log=teardown_log))
    assert second is not None
    assert second is not first
    assert len(teardown_log) == 1


@pytest.mark.asyncio
async def test_teardown_all_adapter_registries_clears_instances():
    teardown_log: list[str] = []
    registry = make_deployment_adapter_registry()
    registry.register_class("local", DummyTeardownAdapter)
    registry.get_instance("local", factory=lambda cls: cls(teardown_log=teardown_log))

    await adapter_registry_mod.teardown_all_adapter_registries()

    assert not registry.has_cached_instances()
    assert len(teardown_log) == 1


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


@pytest.mark.asyncio
async def test_reset_registries_clears_global_state():
    """_reset_registries tears down instances and clears the global registry dict."""
    teardown_log: list[str] = []
    registry = make_deployment_adapter_registry()
    registry.register_class("local", DummyTeardownAdapter)
    registry.get_instance("local", factory=lambda cls: cls(teardown_log=teardown_log))

    await adapter_registry_mod._reset_registries()

    assert len(teardown_log) == 1
    # A new call should create a fresh registry (not the same object).
    new_registry = make_deployment_adapter_registry()
    assert new_registry is not registry
    assert new_registry.list_keys() == []


def test_get_deployment_adapter_triggers_auto_discovery(tmp_path, monkeypatch):
    """get_deployment_adapter should auto-discover from config on first call."""
    from lfx.services.deps import get_deployment_adapter

    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
local = "{__name__}:DummyEntryPointAdapter"
"""
    )
    monkeypatch.setattr(
        "lfx.services.deps._resolve_adapter_config_dir",
        lambda: tmp_path,
    )

    # Registry should not be discovered yet.
    registry = make_deployment_adapter_registry()
    assert not registry.is_discovered

    result = get_deployment_adapter("local")

    assert registry.is_discovered
    assert result is not None
    assert isinstance(result, DummyEntryPointAdapter)
