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
async def test_seed_directory_bundle_loads_at_official_slot(tmp_path: Path, monkeypatch) -> None:
    """A subdirectory under ``$LANGFLOW_SEED_DIR`` registers at @official.

    This is the second production-install source documented in the
    deployment guide.  Without the startup wiring, an operator who copies
    bundles into ``/opt/langflow/bundles/`` (the Mode B/C alternative to
    ``pip install``) sees the docs say it works while no components actually
    appear in the palette.
    """
    import json

    from lfx.extension.bundle_registry import BundleRegistry

    seed_root = tmp_path / "seed-bundles"
    extension_root = seed_root / "lfx-pilot"
    bundle_dir = extension_root / "components"
    bundle_dir.mkdir(parents=True)

    manifest = {
        "id": "lfx-pilot",
        "version": "1.0.0",
        "name": "Pilot",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "pilot", "path": "components"}],
    }
    (extension_root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class PilotThing(Component):\n"
        "    display_name = 'Pilot'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("LANGFLOW_SEED_DIR", str(seed_root))

    fresh_registry = BundleRegistry()
    settings_service = _FakeSettingsService(components_path=[])

    with (
        patch("lfx.interface.components.create_component_template", side_effect=_stub_template),
        patch("lfx.interface.components.get_default_registry", return_value=fresh_registry),
    ):
        result = await import_extension_components(settings_service)

    # Bundle is visible in /api/v1/all
    assert "pilot" in result, f"seed bundle missing from cache; got {list(result)}"
    expected_id = "ext:pilot:PilotThing@official"
    assert expected_id in result["pilot"]
    template = result["pilot"][expected_id]
    assert template["bundle"] == "pilot"
    assert template["extension"] == "lfx-pilot"

    # Bundle is in the BundleRegistry so reload + the events pipeline can find it.
    record = fresh_registry.get_bundle("pilot")
    assert record is not None
    assert record.slot == "official"
    assert record.extension_id == "lfx-pilot"
    assert "PilotThing" in record.class_names


@pytest.mark.asyncio
async def test_seed_bundle_shadowed_by_installed_emits_typed_warning(tmp_path: Path, monkeypatch) -> None:
    """When an installed pip dist shadows a same-named seed bundle, installed wins.

    Per the deployment doc, installed pip distributions take precedence; the
    seed copy is dropped and a typed ``seed-bundle-shadowed`` ExtensionError
    is appended to the seed result so the diagnostics emitter surfaces the
    misconfiguration.  This test asserts both halves: installed wins in the
    BundleRegistry, AND the typed error is attached to the seed result that
    flows through ``_emit_extension_diagnostics``.
    """
    import json

    from lfx.extension.bundle_registry import BundleRegistry

    # Build a seed-directory bundle of the same name as the (faked) install.
    seed_root = tmp_path / "seed-bundles"
    extension_root = seed_root / "lfx-pilot"
    bundle_dir = extension_root / "components"
    bundle_dir.mkdir(parents=True)
    manifest = {
        "id": "lfx-pilot",
        "version": "0.0.1-seed",
        "name": "Pilot (seed)",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "pilot", "path": "components"}],
    }
    (extension_root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class PilotThing(Component):\n"
        "    display_name = 'Seed Pilot'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGFLOW_SEED_DIR", str(seed_root))

    # Build an installed-pkg LoadResult by hand (test seam: stub
    # load_installed_extensions to return a result for bundle "pilot").
    from lfx.extension.loader._types import LoadedComponent, LoadResult

    class _Component:
        pass

    class _InstalledPilotThing(_Component):
        display_name = "Installed Pilot"

        def build(self) -> None:
            return None

    installed_loaded = LoadedComponent(
        extension_id="lfx-pilot",
        extension_version="2.0.0",
        bundle="pilot",
        class_name="PilotThing",
        slot="official",
        klass=_InstalledPilotThing,
        module_name="_lfx_ext.official.pilot.thing",
        file_path=tmp_path / "installed_thing.py",
        distribution="lfx-pilot",
    )
    installed_result = LoadResult(
        slot="official",
        source_path=tmp_path / "installed-extension",
        distribution="lfx-pilot",
    )
    installed_result.extension_id = "lfx-pilot"
    installed_result.extension_version = "2.0.0"
    installed_result.bundle = "pilot"
    installed_result.components = [installed_loaded]

    fresh_registry = BundleRegistry()
    settings_service = _FakeSettingsService(components_path=[])

    captured_diagnostics: list[list] = []

    def _capture_diagnostics(results) -> None:
        captured_diagnostics.append(list(results))

    with (
        patch("lfx.interface.components.create_component_template", side_effect=_stub_template),
        patch("lfx.interface.components.get_default_registry", return_value=fresh_registry),
        patch("lfx.interface.components.load_installed_extensions", return_value=[installed_result]),
        patch("lfx.interface.components._emit_extension_diagnostics", side_effect=_capture_diagnostics),
    ):
        await import_extension_components(settings_service)

    # The installed copy is what registered.
    record = fresh_registry.get_bundle("pilot")
    assert record is not None
    assert record.extension_version == "2.0.0", (
        "installed bundle (v2.0.0) must win over seed-directory shadow (v0.0.1-seed)"
    )
    assert record.distribution == "lfx-pilot"

    # The seed result that ran through the diagnostics emitter carries the
    # typed shadowing error so operators can see the misconfiguration.
    assert captured_diagnostics, "diagnostics emitter was never called"
    all_results = captured_diagnostics[0]
    shadow_codes = {err.code for r in all_results for err in r.errors}
    assert "seed-bundle-shadowed" in shadow_codes, (
        f"expected seed-bundle-shadowed in emitted diagnostics; got codes: {sorted(shadow_codes)}"
    )


@pytest.mark.asyncio
async def test_seed_bundle_shadows_dev_emits_generic_bundle_shadowed(tmp_path: Path, monkeypatch) -> None:
    """A seed bundle silently shadowed a dev registration -- regression for the empty-deltas reload bug.

    Reload reads ``live.source_path`` from the registry and walks that path on
    every call.  Before the cross-source dedup, the registry-population loop in
    :func:`import_extension_components` would silently overwrite earlier records
    with later ones (last-wins iteration order), so a stale dev registration
    pointing at a different filesystem location could clobber the seed record's
    ``source_path``.  Reload would then walk the dev path while the operator
    edits the seed copy on disk: 200 OK with empty deltas every time.

    This test asserts both halves: the seed copy wins in the BundleRegistry
    AND the dev copy gets a typed ``bundle-shadowed`` warning naming both paths.
    """
    import json

    from lfx.extension.bundle_registry import BundleRegistry
    from lfx.extension.loader._types import LoadedComponent, LoadResult

    # Real seed bundle on disk.
    seed_root = tmp_path / "seed-bundles"
    seed_extension_root = seed_root / "lfx-pilot"
    seed_bundle_dir = seed_extension_root / "components"
    seed_bundle_dir.mkdir(parents=True)
    manifest = {
        "id": "lfx-pilot",
        "version": "1.0.0-seed",
        "name": "Pilot (seed)",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "pilot", "path": "components"}],
    }
    (seed_extension_root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    (seed_bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class PilotThing(Component):\n"
        "    display_name = 'Seed'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGFLOW_SEED_DIR", str(seed_root))

    # Faked dev result for the same bundle name pointing at a totally
    # different path -- the stale registration that used to silently win.
    dev_path = tmp_path / "stale-dev-checkout"
    dev_path.mkdir()

    class _Component:
        pass

    class _DevPilotThing(_Component):
        display_name = "Dev"

        def build(self) -> None:
            return None

    dev_loaded = LoadedComponent(
        extension_id="lfx-pilot",
        extension_version="9.9.9-dev",
        bundle="pilot",
        class_name="PilotThing",
        slot="official",
        klass=_DevPilotThing,
        module_name="_lfx_ext.official.pilot.thing",
        file_path=dev_path / "thing.py",
        distribution=None,
    )
    dev_result = LoadResult(slot="official", source_path=dev_path)
    dev_result.extension_id = "lfx-pilot"
    dev_result.extension_version = "9.9.9-dev"
    dev_result.bundle = "pilot"
    dev_result.components = [dev_loaded]

    fresh_registry = BundleRegistry()
    settings_service = _FakeSettingsService(components_path=[])

    captured_diagnostics: list[list] = []

    def _capture_diagnostics(results) -> None:
        captured_diagnostics.append(list(results))

    with (
        patch("lfx.interface.components.create_component_template", side_effect=_stub_template),
        patch("lfx.interface.components.get_default_registry", return_value=fresh_registry),
        patch("lfx.interface.components.load_dev_extensions", return_value=[dev_result]),
        patch("lfx.interface.components._emit_extension_diagnostics", side_effect=_capture_diagnostics),
    ):
        await import_extension_components(settings_service)

    # Seed wins (higher precedence than dev).  The crucial assertion: the
    # registry's source_path is the seed path, NOT the stale dev path -- so
    # reload will walk the right directory and pick up on-disk edits.
    record = fresh_registry.get_bundle("pilot")
    assert record is not None
    assert record.extension_version == "1.0.0-seed", "seed bundle must win over dev shadow"
    assert record.source_path is not None
    assert record.source_path.resolve() == seed_extension_root.resolve(), (
        f"registry source_path={record.source_path} must point at the seed copy "
        f"at {seed_extension_root}, not the stale dev path {dev_path}; otherwise "
        "POST /reload silently no-ops on edits to the seed copy"
    )

    # The dev result that ran through the diagnostics emitter carries the
    # generic typed shadow warning naming both paths.
    assert captured_diagnostics, "diagnostics emitter was never called"
    all_results = captured_diagnostics[0]
    shadow_errors = [err for r in all_results for err in r.errors if err.code == "bundle-shadowed"]
    assert len(shadow_errors) == 1, (
        f"expected exactly one bundle-shadowed warning; got {[e.code for r in all_results for e in r.errors]}"
    )
    msg = shadow_errors[0].message
    assert str(dev_path) in msg, msg
    assert str(seed_extension_root) in msg, msg


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


def test_post_swap_hook_invalidates_hash_lookups(tmp_path: Path) -> None:
    """After reload, the precomputed hash lookups must be invalidated.

    ``flow_validation.get_component_hash_lookups_for_validation`` only
    rebuilds the maps when both fields are None.  Without invalidation,
    flows running with custom components disabled keep validating against
    pre-reload class bodies and reject post-reload code as "unrecognized".
    """
    from lfx.extension.bundle_registry import BundleRecord
    from lfx.extension.loader._types import LoadedComponent
    from lfx.interface.components import (
        component_cache,
        refresh_bundle_cache_from_record,
    )

    component_cache.all_types_dict = {"delta": {"old": {"display_name": "old"}}}
    component_cache.type_to_current_hash = {"DeltaThing": {"abc123def456"}}  # pragma: allowlist secret
    component_cache.all_known_hashes = {"abc123def456"}  # pragma: allowlist secret

    class _Component:
        pass

    class _DeltaThing(_Component):
        display_name = "Delta"

        def build(self) -> None:
            return None

    loaded = LoadedComponent(
        extension_id="lfx-delta",
        extension_version="1.0.0",
        bundle="delta",
        class_name="DeltaThing",
        slot="official",
        klass=_DeltaThing,
        module_name="_lfx_ext.official.delta.thing",
        file_path=tmp_path / "thing.py",
        distribution=None,
    )
    record = BundleRecord(
        bundle="delta",
        extension_id="lfx-delta",
        extension_version="1.0.0",
        slot="official",
        components=(loaded,),
    )

    with patch("lfx.interface.components.create_component_template", side_effect=_stub_template):
        refresh_bundle_cache_from_record(record)

    assert component_cache.type_to_current_hash is None
    assert component_cache.all_known_hashes is None


def test_refresh_cache_preserves_entry_on_total_failure(tmp_path: Path) -> None:
    """Total template failure preserves the previous cache entry and raises.

    Refuse to overwrite the previous cache entry with ``{}``; raise so the
    hook layer can surface the failure on ``ReloadResult.warnings``.
    Regression guard for the empty-palette-after-reload bug: the prior code
    silently logged a warning per failed component, then unconditionally
    wrote an empty dict to ``component_cache.all_types_dict[bundle]``.
    """
    from lfx.extension.bundle_registry import BundleRecord
    from lfx.extension.loader._types import LoadedComponent
    from lfx.interface.components import (
        component_cache,
        refresh_bundle_cache_from_record,
    )

    pre_existing = {"ext:zeta:OldThing@official": {"display_name": "old", "extension": "lfx-zeta"}}
    component_cache.all_types_dict = {"zeta": dict(pre_existing)}

    class _Component:
        pass

    class _ZetaThing(_Component):
        display_name = "Zeta"

        def build(self) -> None:
            return None

    loaded = LoadedComponent(
        extension_id="lfx-zeta",
        extension_version="1.0.0",
        bundle="zeta",
        class_name="ZetaThing",
        slot="official",
        klass=_ZetaThing,
        module_name="_lfx_ext.official.zeta.thing",
        file_path=tmp_path / "thing.py",
        distribution=None,
    )
    record = BundleRecord(
        bundle="zeta",
        extension_id="lfx-zeta",
        extension_version="1.0.0",
        slot="official",
        components=(loaded,),
    )

    def _always_raises(*_args, **_kwargs):
        msg = "synthetic template failure"
        raise RuntimeError(msg)

    with (
        patch("lfx.interface.components.create_component_template", side_effect=_always_raises),
        pytest.raises(RuntimeError, match="every component in bundle 'zeta' failed to template"),
    ):
        refresh_bundle_cache_from_record(record)

    # Pre-existing cache entry untouched -- the palette continues to show
    # the pre-reload component set instead of going dark.
    assert component_cache.all_types_dict["zeta"] == pre_existing


def test_refresh_cache_writes_partial_on_partial_failure(tmp_path: Path) -> None:
    """One passing + one failing component commits a partial cache entry.

    Palette is "less broken" than pre-reload; the bundle dict must not be
    empty (otherwise the total-failure guard would have raised).
    """
    from lfx.extension.bundle_registry import BundleRecord
    from lfx.extension.loader._types import LoadedComponent
    from lfx.interface.components import (
        component_cache,
        refresh_bundle_cache_from_record,
    )

    component_cache.all_types_dict = {"eta": {}}

    class _Component:
        pass

    class _Good(_Component):
        display_name = "Good"

        def build(self) -> None:
            return None

    class _Bad(_Component):
        display_name = "Bad"

        def build(self) -> None:
            return None

    good = LoadedComponent(
        extension_id="lfx-eta",
        extension_version="1.0.0",
        bundle="eta",
        class_name="Good",
        slot="official",
        klass=_Good,
        module_name="_lfx_ext.official.eta.good",
        file_path=tmp_path / "good.py",
        distribution=None,
    )
    bad = LoadedComponent(
        extension_id="lfx-eta",
        extension_version="1.0.0",
        bundle="eta",
        class_name="Bad",
        slot="official",
        klass=_Bad,
        module_name="_lfx_ext.official.eta.bad",
        file_path=tmp_path / "bad.py",
        distribution=None,
    )
    record = BundleRecord(
        bundle="eta",
        extension_id="lfx-eta",
        extension_version="1.0.0",
        slot="official",
        components=(good, bad),
    )

    def _template(component_extractor, module_name=None):  # noqa: ARG001
        if isinstance(component_extractor, _Bad):
            msg = "synthetic per-component failure"
            raise RuntimeError(msg)  # noqa: TRY004
        return _stub_template()

    with patch("lfx.interface.components.create_component_template", side_effect=_template):
        refresh_bundle_cache_from_record(record)

    bundle_dict = component_cache.all_types_dict["eta"]
    assert "ext:eta:Good@official" in bundle_dict
    assert "ext:eta:Bad@official" not in bundle_dict


@pytest.mark.asyncio
async def test_dev_extension_components_loaded_via_official_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dev extensions registered via ``lfx extension dev`` must enter the @official pathway.

    Earlier wiring appended their bundle directories to LANGFLOW_COMPONENTS_PATH,
    causing them to fall back to legacy custom-component loading without
    extension metadata or BundleRegistry entries.  Now they share the same
    pathway as installed extensions.
    """
    import json

    from lfx.extension import register_dev_extension
    from lfx.extension.bundle_registry import BundleRegistry

    # Build a manifest-shipping extension on disk.
    ext_root = tmp_path / "my-ext"
    ext_root.mkdir()
    bundle_dir = ext_root / "components"
    bundle_dir.mkdir()
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\n"
        "class DevThing(Component):\n"
        "    display_name = 'Dev'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )
    (ext_root / "extension.json").write_text(
        json.dumps(
            {
                "id": "lfx-dev-fixture",
                "version": "0.1.0",
                "name": "Dev Fixture",
                "lfx": {"compat": ["1"]},
                "bundles": [{"name": "devbundle", "path": "components"}],
            }
        ),
        encoding="utf-8",
    )

    # Point the dev registry at an isolated state file via env var so the
    # test does not pollute the user's real cache dir.
    monkeypatch.setenv("LANGFLOW_DEV_EXTENSIONS_DIR", str(tmp_path / "registry"))
    register_dev_extension(ext_root)

    fresh_registry = BundleRegistry()
    settings_service = _FakeSettingsService(components_path=[])

    with (
        patch("lfx.interface.components.create_component_template", side_effect=_stub_template),
        patch("lfx.interface.components.get_default_registry", return_value=fresh_registry),
    ):
        result = await import_extension_components(settings_service)

    assert "devbundle" in result
    record = fresh_registry.get_bundle("devbundle")
    assert record is not None
    assert record.slot == "official"
    assert "DevThing" in record.class_names
    expected_id = "ext:devbundle:DevThing@official"
    assert expected_id in result["devbundle"]
    assert result["devbundle"][expected_id]["extension"] == "lfx-dev-fixture"
