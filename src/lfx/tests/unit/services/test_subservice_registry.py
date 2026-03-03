"""Tests for generic sub-service registry and discovery."""

from __future__ import annotations

from pathlib import Path, PurePath

import pytest
from lfx.services import subservice as subservice_mod


class DummyDecoratorAdapter:
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
        lambda group: [DummyEntryPoint("local", Path)] if group == "lfx.deployment.adapters" else [],
    )

    # Decorator registration should override entry point.
    subservice_mod.register_sub_service("deployment.adapters", "local")(DummyDecoratorAdapter)

    # Config should override decorator registration.
    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "pathlib:PurePath"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("local") is PurePath


def test_lfx_toml_takes_precedence_over_pyproject(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "pathlib:Path"
"""
    )
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.lfx.deployment.adapters]
local = "pathlib:PurePath"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("local") is Path


def test_discover_only_once(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "pathlib:Path"
"""
    )
    registry.discover_sub_services(config_dir=tmp_path)
    assert registry.get_sub_service_class("local") is Path

    # Change config after first discovery should have no effect.
    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "pathlib:PurePath"
"""
    )
    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("local") is Path


def test_invalid_import_path_is_ignored(tmp_path):
    registry = _registry()

    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters]
local = "invalid_without_colon"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("local") is None


def test_register_sub_service_class_override_false_preserves_existing():
    registry = _registry()
    registry.register_sub_service_class("local", Path, override=True)
    registry.register_sub_service_class("local", PurePath, override=False)

    assert registry.get_sub_service_class("local") is Path


def test_list_sub_service_keys_is_sorted():
    registry = _registry()
    registry.register_sub_service_class("zeta", Path)
    registry.register_sub_service_class("alpha", PurePath)

    assert registry.list_sub_service_keys() == ["alpha", "zeta"]


def test_pyproject_only_discovery(tmp_path):
    registry = _registry()
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.lfx.deployment.adapters]
local = "pathlib:Path"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)

    assert registry.get_sub_service_class("local") is Path


def test_discovery_handles_malformed_toml(tmp_path):
    registry = _registry()
    (tmp_path / "lfx.toml").write_text(
        """
[deployment.adapters
local = "pathlib:Path"
"""
    )

    # Should not raise
    registry.discover_sub_services(config_dir=tmp_path)
    assert registry.get_sub_service_class("local") is None


def test_discovery_ignores_missing_or_empty_section(tmp_path):
    registry = _registry()
    (tmp_path / "lfx.toml").write_text(
        """
[other]
key = "value"
"""
    )

    registry.discover_sub_services(config_dir=tmp_path)
    assert registry.list_sub_service_keys() == []


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
        """
[deployment.adapters]
local = "pathlib:Path"
"""
    )

    # Should still discover config entry even if entry point loading fails.
    registry.discover_sub_services(config_dir=tmp_path)
    assert registry.get_sub_service_class("local") is Path


def test_get_nested_section_returns_none_for_non_dict_path():
    nested = {"tool": {"lfx": {"deployment": "not-a-dict"}}}

    section = subservice_mod._get_nested_section(nested, ("tool", "lfx", "deployment", "adapters"))
    assert section is None


def test_get_sub_service_registry_warns_on_parameter_mismatch(monkeypatch):
    first = _registry()

    warnings: list[str] = []
    monkeypatch.setattr(subservice_mod.logger, "warning", lambda msg: warnings.append(str(msg)))

    second = subservice_mod.get_sub_service_registry(
        namespace="deployment.adapters",
        entry_point_group="lfx.OTHER.group",
        config_section_path=("other", "path"),
    )

    assert second is first
    assert len(warnings) == 1
    assert "different parameters" in warnings[0]
