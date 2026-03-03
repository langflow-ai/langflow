"""Tests for generic adapter registry and discovery."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from lfx.services import adapter_registry as adapter_registry_mod
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


class DummyDecoratorAdapter(_DeploymentAdapterStub):
    pass


class DummyEntryPointAdapter(_DeploymentAdapterStub):
    pass


class DummyConfigAdapter(_DeploymentAdapterStub):
    pass


class DummyAlternateAdapter(_DeploymentAdapterStub):
    pass


class DummyTeardownAdapter(_DeploymentAdapterStub):
    teardown_calls = 0

    async def teardown(self):
        type(self).teardown_calls += 1


class DummyEntryPoint:
    """Simple entry point stub for importlib.metadata.entry_points()."""

    def __init__(self, name: str, obj: type):
        self.name = name
        self._obj = obj

    def load(self):
        return self._obj


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


def test_get_adapter_registry_singleton():
    first = _registry()
    second = _registry()

    assert first is second


def test_get_adapter_registry_raises_on_parameter_mismatch_for_same_adapter_type():
    _registry()

    with pytest.raises(adapter_registry_mod.AdapterRegistryConflictError):
        adapter_registry_mod.get_adapter_registry(
            adapter_type=AdapterType.DEPLOYMENT,
            entry_point_group="lfx.OTHER.group",
            config_section_path=("other", "path"),
        )


def test_discovery_precedence_entrypoint_decorator_config(tmp_path, monkeypatch):
    registry = _registry()

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda group: [DummyEntryPoint("local", DummyEntryPointAdapter)] if group == "lfx.deployment.adapters" else [],
    )

    adapter_registry_mod.register_adapter(AdapterType.DEPLOYMENT, "local")(DummyDecoratorAdapter)

    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
local = "{__name__}:DummyConfigAdapter"
"""
    )

    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is DummyConfigAdapter


def test_lfx_toml_takes_precedence_over_pyproject(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
local = "{__name__}:DummyConfigAdapter"
"""
    )
    (tmp_path / "pyproject.toml").write_text(
        f"""
[tool.lfx.deployment.adapters]
local = "{__name__}:DummyAlternateAdapter"
"""
    )

    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is DummyConfigAdapter


def test_discover_only_once(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
local = "{__name__}:DummyConfigAdapter"
"""
    )
    registry.discover(config_dir=tmp_path)
    assert registry.get_class("local") is DummyConfigAdapter

    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
local = "{__name__}:DummyAlternateAdapter"
"""
    )
    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is DummyConfigAdapter


def test_invalid_import_path_is_ignored(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "invalid_without_colon"
"""
    )

    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is None


def test_register_class_override_false_preserves_existing():
    registry = _registry()
    registry.register_class("local", DummyEntryPointAdapter, override=True)
    registry.register_class("local", DummyDecoratorAdapter, override=False)

    assert registry.get_class("local") is DummyEntryPointAdapter


def test_decorator_override_false_preserves_entrypoint(tmp_path, monkeypatch):
    registry = _registry()
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda group: [DummyEntryPoint("local", DummyEntryPointAdapter)] if group == "lfx.deployment.adapters" else [],
    )
    adapter_registry_mod.register_adapter(
        AdapterType.DEPLOYMENT,
        "local",
        override=False,
    )(DummyDecoratorAdapter)

    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is DummyEntryPointAdapter


def test_decorator_override_false_skips_when_same_key_already_decorated(tmp_path):
    adapter_registry_mod.register_adapter(AdapterType.DEPLOYMENT, "local")(DummyDecoratorAdapter)
    adapter_registry_mod.register_adapter(AdapterType.DEPLOYMENT, "local", override=False)(DummyAlternateAdapter)

    registry = _registry()
    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is DummyDecoratorAdapter


def test_list_keys_is_sorted():
    registry = _registry()
    registry.register_class("zeta", DummyEntryPointAdapter)
    registry.register_class("alpha", DummyDecoratorAdapter)

    assert registry.list_keys() == ["alpha", "zeta"]


def test_repr_before_and_after_discovery(tmp_path):
    registry = _registry()
    registry.register_class("local", DummyEntryPointAdapter)

    r = repr(registry)
    assert "adapter_type=<AdapterType.DEPLOYMENT: 'deployment'>" in r
    assert "keys=['local']" in r
    assert "discovered=False" in r

    registry.discover(config_dir=tmp_path)
    assert "discovered=True" in repr(registry)


def test_pyproject_only_discovery(tmp_path):
    registry = _registry()
    (tmp_path / "pyproject.toml").write_text(
        f"""
[tool.lfx.deployment.adapters]
local = "{__name__}:DummyConfigAdapter"
"""
    )

    registry.discover(config_dir=tmp_path)

    assert registry.get_class("local") is DummyConfigAdapter


def test_discovery_handles_malformed_toml(tmp_path):
    registry = _registry()
    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters
local = "pathlib:Path"
"""
    )

    registry.discover(config_dir=tmp_path)
    assert registry.get_class("local") is None


def test_discovery_ignores_missing_or_empty_section(tmp_path):
    registry = _registry()
    (tmp_path / "lfx.toml").write_text(
        """
[other]
key = "value"
"""
    )

    registry.discover(config_dir=tmp_path)
    assert registry.list_keys() == []


def test_entry_point_load_failure_does_not_abort_discovery(tmp_path, monkeypatch):
    registry = _registry()

    class BrokenEntryPoint:
        name = "broken"

        def load(self):
            msg = "boom"
            raise RuntimeError(msg)

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda group: [BrokenEntryPoint()] if group == "lfx.deployment.adapters" else [],
    )
    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
local = "{__name__}:DummyConfigAdapter"
"""
    )

    registry.discover(config_dir=tmp_path)
    assert registry.get_class("local") is DummyConfigAdapter


def test_get_nested_section_returns_none_for_non_dict_path():
    nested = {"tool": {"lfx": {"deployment": "not-a-dict"}}}

    section = adapter_registry_mod._get_nested_section(nested, ("tool", "lfx", "deployment", "adapters"))
    assert section is None


# --- Import / attribute error paths ---


def test_config_with_nonexistent_module_is_ignored(tmp_path):
    """Config referencing a module that cannot be imported is silently skipped."""
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "nonexistent_pkg_xyz.adapters:Adapter"
"""
    )

    registry.discover(config_dir=tmp_path)
    assert registry.get_class("local") is None


def test_config_with_nonexistent_class_in_valid_module_is_ignored(tmp_path):
    """Config referencing a real module but missing class is silently skipped."""
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "pathlib:TotallyMadeUpClassName"
"""
    )

    registry.discover(config_dir=tmp_path)
    assert registry.get_class("local") is None


# --- Additional coverage ---


def test_config_with_non_string_value_is_ignored(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = 42
"""
    )

    registry.discover(config_dir=tmp_path)
    assert registry.get_class("local") is None


def test_multi_key_discovery_across_sources(tmp_path, monkeypatch):
    registry = _registry()

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda group: (
            [DummyEntryPoint("ep_only", DummyEntryPointAdapter)] if group == "lfx.deployment.adapters" else []
        ),
    )

    adapter_registry_mod.register_adapter(AdapterType.DEPLOYMENT, "dec_only")(DummyDecoratorAdapter)

    (tmp_path / "lfx.toml").write_text(
        f"""
[deployment.adapters]
cfg_only = "{__name__}:DummyConfigAdapter"
"""
    )

    registry.discover(config_dir=tmp_path)

    assert registry.get_class("ep_only") is DummyEntryPointAdapter
    assert registry.get_class("dec_only") is DummyDecoratorAdapter
    assert registry.get_class("cfg_only") is DummyConfigAdapter
    assert registry.list_keys() == ["cfg_only", "dec_only", "ep_only"]


def test_get_deployment_registry_returns_singleton():
    from lfx.services.deps import get_deployment_registry

    first = get_deployment_registry()
    second = get_deployment_registry()

    assert first is second
    assert first.adapter_type == AdapterType.DEPLOYMENT
    assert first.entry_point_group == "lfx.deployment.adapters"
    assert first.config_section_path == ("deployment", "adapters")


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


def test_get_instance_is_thread_safe_singleton_creation():
    registry = _registry()
    registry.register_class("local", DummyEntryPointAdapter)
    factory_calls = 0
    factory_lock = threading.Lock()

    def factory(adapter_class):
        nonlocal factory_calls
        with factory_lock:
            factory_calls += 1
        return adapter_class()

    def resolve_instance(_):
        return registry.get_instance("local", factory=factory)

    with ThreadPoolExecutor(max_workers=8) as pool:
        instances = list(pool.map(resolve_instance, range(50)))

    assert instances
    first = instances[0]
    assert first is not None
    assert all(instance is first for instance in instances)
    assert factory_calls == 1


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
    from lfx.services.deps import get_deployment_adapter, get_deployment_registry

    registry = get_deployment_registry()
    registry.register_class("unit", DummyEntryPointAdapter)

    first = get_deployment_adapter("unit")
    second = get_deployment_adapter("unit")

    assert first is not None
    assert first is second
