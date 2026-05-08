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


@pytest.mark.asyncio
async def test_import_extension_components_populates_bundle_registry(tmp_path: Path) -> None:
    """Startup wiring: discovered bundles must be installed in the BundleRegistry.

    Without this, a real POST /api/v1/extensions/{id}/bundles/{name}/reload
    returns ``reload-bundle-not-installed`` for bundles that ARE visible in
    the palette, because the reload endpoint reads a separate registry that
    nothing populates.
    """
    from lfx.extension.bundle_registry import BundleRegistry, get_default_registry

    parent = tmp_path / "components_root"
    bundle_dir = parent / "beta"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class BetaThing(Component):\n"
        "    display_name = 'Beta'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )

    # Replace the process-default registry with a fresh one for this test
    # so we don't observe state from earlier tests in the suite.
    fresh_registry = BundleRegistry()
    settings_service = _FakeSettingsService(components_path=[str(parent)])

    with (
        patch("lfx.interface.components.create_component_template", side_effect=_stub_template),
        patch("lfx.interface.components.get_default_registry", return_value=fresh_registry),
    ):
        await import_extension_components(settings_service)

    record = fresh_registry.get_bundle("beta")
    assert record is not None, "bundle 'beta' must be registered after import"
    assert record.bundle == "beta"
    assert record.slot == "extra"
    # The class should be visible in the registry too (so reload's diff works).
    assert "BetaThing" in record.class_names

    # Sanity: get_default_registry() unmocked is also still callable.
    assert get_default_registry() is not None


def test_post_swap_hook_refreshes_component_cache(tmp_path: Path) -> None:
    """After reload_bundle's Stage-3 swap, the component cache picks up the new class set.

    Without the post-swap hook, ``component_cache.all_types_dict`` keeps the
    pre-reload templates and the palette / new-graph path stays stale until
    the next server restart.
    """
    from lfx.extension.bundle_registry import BundleRecord
    from lfx.extension.loader._types import LoadedComponent
    from lfx.interface.components import (
        component_cache,
        refresh_bundle_cache_from_record,
    )

    # Seed the cache with a placeholder pre-reload template for bundle 'gamma'.
    component_cache.all_types_dict = {"gamma": {"old": {"display_name": "old"}}}

    # Build a BundleRecord with a fake LoadedComponent.  We use the same
    # toy Component shim the other tests use; create_component_template
    # would fail on it, so patch the builder to return a stub.
    class _Component:
        pass

    class _GammaThing(_Component):
        display_name = "Gamma"

        def build(self) -> None:
            return None

    loaded = LoadedComponent(
        extension_id="lfx-gamma",
        extension_version="1.0.0",
        bundle="gamma",
        class_name="GammaThing",
        slot="official",
        klass=_GammaThing,
        module_name="_lfx_ext.official.gamma.thing",
        file_path=tmp_path / "thing.py",
        distribution=None,
    )
    record = BundleRecord(
        bundle="gamma",
        extension_id="lfx-gamma",
        extension_version="1.0.0",
        slot="official",
        components=(loaded,),
    )

    with patch("lfx.interface.components.create_component_template", side_effect=_stub_template):
        refresh_bundle_cache_from_record(record)

    assert "gamma" in component_cache.all_types_dict
    assert "old" not in component_cache.all_types_dict["gamma"], (
        "post-swap refresh must replace the pre-reload bundle dict, not merge"
    )
    expected_id = "ext:gamma:GammaThing@official"
    assert expected_id in component_cache.all_types_dict["gamma"]


def test_post_swap_hook_noop_when_cache_not_built() -> None:
    """If the cache hasn't been built yet, the hook must be a safe no-op.

    The first ``get_and_cache_all_types_dict`` call will see the fresh
    registry entry and pick up the post-reload class set; we don't want
    the hook to crash on a None cache.
    """
    from lfx.extension.bundle_registry import BundleRecord
    from lfx.interface.components import (
        component_cache,
        refresh_bundle_cache_from_record,
    )

    component_cache.all_types_dict = None
    record = BundleRecord(
        bundle="empty",
        extension_id="lfx-empty",
        extension_version="1.0.0",
        slot="official",
        components=(),
    )
    # Must not raise.
    refresh_bundle_cache_from_record(record)
    assert component_cache.all_types_dict is None
