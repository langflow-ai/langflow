"""Concurrency tests for generic adapter registry."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

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
