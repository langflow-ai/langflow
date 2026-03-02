"""Tests for generic sub-service registry and discovery."""

from __future__ import annotations

from pathlib import Path, PurePath

import pytest
from lfx.services import subservice as subservice_mod


class DummyDecoratorAdapter:
    pass


class DummyDecoratorOverrideAdapter:
    pass


class DummyEntryPoint:
    """Simple entry point stub for importlib.metadata.entry_points()."""

    def __init__(self, name: str, obj: type):
        self.name = name
        self._obj = obj

    def load(self):
        return self._obj


@pytest.fixture(autouse=True)
def clean_subservice_globals():
    """Ensure global registry state is isolated per test."""
    subservice_mod._decorator_subservice_registry.clear()
    subservice_mod._subservice_registries.clear()
    yield
    subservice_mod._decorator_subservice_registry.clear()
    subservice_mod._subservice_registries.clear()


def _registry():
    return subservice_mod.get_sub_service_registry(
        namespace="deployment.adapters",
        entry_point_group="lfx.deployment.adapters",
        config_section_path=("deployment", "adapters"),
    )


def test_get_sub_service_registry_singleton():
    first = _registry()
    second = _registry()

    assert first is second


def test_discovery_precedence_entrypoint_decorator_config(tmp_path, monkeypatch):
    registry = _registry()

    # Entry point provides one adapter class.
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda group: [DummyEntryPoint("watsonx-orchestrate", Path)] if group == "lfx.deployment.adapters" else [],
    )

    # Decorator registration should override entry point.
    subservice_mod.register_sub_service("deployment.adapters", "watsonx-orchestrate")(DummyDecoratorAdapter)

    # Config should override decorator registration.
    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
watsonx-orchestrate = "pathlib:PurePath"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("watsonx-orchestrate") is PurePath


def test_lfx_toml_takes_precedence_over_pyproject(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
watsonx-orchestrate = "pathlib:Path"
"""
    )
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.lfx.deployment.adapters]
watsonx-orchestrate = "pathlib:PurePath"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("watsonx-orchestrate") is Path


def test_discover_only_once(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
watsonx-orchestrate = "pathlib:Path"
"""
    )
    registry.discover_sub_services(config_dir=tmp_path)
    assert registry.get_sub_service_class("watsonx-orchestrate") is Path

    # Change config after first discovery should have no effect.
    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
watsonx-orchestrate = "pathlib:PurePath"
"""
    )
    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("watsonx-orchestrate") is Path


def test_invalid_import_path_is_ignored(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
watsonx-orchestrate = "invalid_without_colon"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("watsonx-orchestrate") is None
