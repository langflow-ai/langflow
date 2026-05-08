"""Integration tests for the Extension System -> /all cache wiring.

Verifies that ``import_extension_components`` produces a dict shaped like
``{bundle_name: {class_name: template}}`` with ``extension``, ``bundle``,
and ``extension_version`` populated -- the AC for ``/api/v1/all``
visibility.

The toy Component classes used by the loader's other test fixtures don't
inherit from the real ``lfx.custom.custom_component.component.Component``
base, so ``create_component_template`` fails on them. We exercise that
"skip on template-build failure" path AND patch the template-builder for a
positive assertion that the fields are stamped onto the produced template.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from lfx.interface.components import (
    _decorate_template_with_extension,
    import_extension_components,
)

if TYPE_CHECKING:
    from pathlib import Path


class _FakeSettings:
    components_path: list[str]


class _FakeSettingsService:
    def __init__(self, components_path: list[str] | None = None) -> None:
        self.settings = _FakeSettings()
        self.settings.components_path = components_path or []


def _stub_template(*_args, **_kwargs) -> tuple[dict[str, Any], object]:
    """Stand-in for ``create_component_template`` that returns a minimal dict.

    Mirrors the shape downstream consumers depend on: a ``display_name``
    plus the field set the cache merges. The instance is unused by the
    decorator, so a sentinel object is sufficient.
    """
    return ({"display_name": "Stub", "type": "stub", "template": {}}, object())


def test_decorate_template_stamps_required_fields() -> None:
    """The AC fields land on the template dict as top-level keys."""
    template = {"display_name": "X"}
    decorated = _decorate_template_with_extension(
        template,
        extension_id="lfx-pilot",
        bundle="pilot",
        extension_version="1.2.3",
        namespaced_id="ext:pilot:PilotThing@official",
    )
    assert decorated["extension"] == "lfx-pilot"
    assert decorated["bundle"] == "pilot"
    assert decorated["extension_version"] == "1.2.3"
    assert decorated["namespaced_id"] == "ext:pilot:PilotThing@official"
    # Existing keys are preserved.
    assert decorated["display_name"] == "X"


@pytest.mark.asyncio
async def test_import_extension_components_returns_empty_when_nothing_to_load() -> None:
    """No installed extensions and no inline paths -> empty mapping."""
    settings_service = _FakeSettingsService(components_path=[])
    result = await import_extension_components(settings_service)
    assert result == {}


@pytest.mark.asyncio
async def test_inline_bundle_components_decorated_with_extension_metadata(tmp_path: Path) -> None:
    """End-to-end: an inline bundle directory produces decorated templates.

    Uses a stubbed ``create_component_template`` so the test doesn't
    require the real heavyweight Component base. The loader's discovery
    layer is exercised for real.
    """
    parent = tmp_path / "components_root"
    bundle_dir = parent / "alpha"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class AlphaThing(Component):\n"
        "    display_name = 'Alpha'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )

    settings_service = _FakeSettingsService(components_path=[str(parent)])

    with patch("lfx.interface.components.create_component_template", side_effect=_stub_template):
        result = await import_extension_components(settings_service)

    assert "alpha" in result
    # AC: components are registered under ``ext:<bundle>:<Class>@<slot>``,
    # NOT under the bare class name.
    expected_id = "ext:alpha:AlphaThing@extra"
    assert expected_id in result["alpha"], (
        f"Expected namespaced ID {expected_id!r} as dict key; got {list(result['alpha'])}"
    )
    assert "AlphaThing" not in result["alpha"], (
        "Bare class name must NOT be the registry key (would collide with built-in IDs)"
    )
    template = result["alpha"][expected_id]
    assert template["bundle"] == "alpha"
    assert template["extension"]  # id derived from bundle.json or default
    assert template["extension_version"]  # default "0.0.0" when no bundle.json
    assert template["namespaced_id"] == expected_id


@pytest.mark.asyncio
async def test_template_failure_skips_component_without_aborting_bundle(tmp_path: Path) -> None:
    """A class that fails to instantiate / template doesn't abort the bundle.

    The toy ``Component`` base in the source file lacks the heavyweight
    machinery that ``create_component_template`` needs, so the real builder
    raises -- this is the "skip with logged warning" path. We let it run
    without the stub to verify the defensive try/except.
    """
    parent = tmp_path / "components_root"
    bundle_dir = parent / "alpha"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class AlphaThing(Component):\n"
        "    display_name = 'Alpha'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )

    settings_service = _FakeSettingsService(components_path=[str(parent)])
    # No patch: real create_component_template will raise for the toy class.
    result = await import_extension_components(settings_service)
    # Bundle is registered, but no class survives template build.
    assert result == {} or result.get("alpha") == {}


@pytest.mark.asyncio
async def test_components_path_empty_string_does_not_crash(monkeypatch) -> None:
    """Pathsep parsing edge case: empty segments don't break the inline walk."""
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", os.pathsep)
    settings_service = _FakeSettingsService(components_path=[])
    # No patch needed -- there's nothing to load.
    result = await import_extension_components(settings_service)
    assert result == {}
