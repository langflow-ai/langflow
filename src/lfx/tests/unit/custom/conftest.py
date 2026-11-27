"""Shared fixtures for the component class cache tests."""

import inspect

import pytest
from lfx.custom import class_cache


@pytest.fixture(autouse=True)
def _clean_cache():
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()
    yield
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()


@pytest.fixture
def cache_on(monkeypatch):
    """Enable the cache with a clean slate."""
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)
    # Treat every source as reviewed and trusted so these tests exercise the cache; both gates have own tests.
    monkeypatch.setattr(class_cache, "_is_reviewed", lambda _digest, _name: True)
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda _code: True)


def _class_state(component_class: type) -> dict[str, dict[str, tuple[int, str]]]:
    """Identity and repr of every class attribute and module-level value: catches rebinding and in-place changes."""
    namespace = next((f.__globals__ for f in vars(component_class).values() if inspect.isfunction(f)), None)
    assert namespace is not None, f"{component_class.__name__} defines no methods"

    def snapshot(values: dict) -> dict[str, tuple[int, str]]:
        return {k: (id(v), repr(v)) for k, v in values.items() if not k.startswith("__")}

    return {"class": snapshot(vars(component_class)), "module": snapshot(namespace)}


@pytest.fixture
def class_state():
    """``class_state(cls)`` snapshots a component class so a test can assert nothing wrote onto it."""
    return _class_state
