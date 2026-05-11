"""Concurrency tests for generic adapter registry."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.unit.services.adapter_test_helpers import DeploymentAdapterStub, make_deployment_adapter_registry


class DummyEntryPointAdapter(DeploymentAdapterStub):
    pass


pytestmark = pytest.mark.usefixtures("clean_adapter_globals")


def test_get_instance_is_thread_safe_singleton_creation():
    registry = make_deployment_adapter_registry()
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


def test_discover_is_thread_safe_runs_inner_discovery_once(tmp_path, monkeypatch):
    registry = make_deployment_adapter_registry()
    call_count = 0
    call_count_lock = threading.Lock()

    def counted_entry_points():
        nonlocal call_count
        time.sleep(0.02)
        with call_count_lock:
            call_count += 1

    monkeypatch.setattr(registry, "_discover_from_entry_points", counted_entry_points)
    monkeypatch.setattr(registry, "_discover_from_config", lambda **_: None)

    def run_discover(_):
        registry.discover(config_dir=tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(run_discover, range(8)))

    assert registry.is_discovered is True
    assert call_count == 1
