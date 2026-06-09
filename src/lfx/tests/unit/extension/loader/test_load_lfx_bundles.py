"""Tests for ``load_lfx_bundles_extensions`` -- the manifest-less @official source.

The third @official-slot production source after installed-manifest and
seed-directory bundles. A distribution declares ``[project.entry-points."lfx.bundles"]``
pointing at a package whose immediate subdirectories are each a bundle,
registered at @official with no ``extension.json`` (the langchain-community
model). Covers:

  - a resolved bundle root registers each provider subdirectory at @official;
  - an entry-point declaration that does not resolve to a package directory
    yields a ``bundle-discovery-malformed`` *warning* and never raises;
  - a manifest source shadows a same-named manifest-less provider with a
    ``bundle-shadowed`` warning (the graduate-with-no-lockstep property),
    verified through ``_resolve_bundle_shadowing`` directly.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from lfx.extension import SLOT_OFFICIAL, LoadedComponent, LoadResult, load_lfx_bundles_extensions
from lfx.extension.loader._bundles_root import (
    LFX_BUNDLES_ENTRY_POINT_GROUP,
    _BundleRoot,
    _load_bundle_roots,
    _resolve_bundle_roots,
)
from lfx.interface.components import _resolve_bundle_shadowing

from .conftest import component_source


class _FakeBundlesEntryPoint:
    """An ``lfx.bundles`` entry point stand-in carrying ``name``/``value``/``dist``.

    ``value`` is the dotted package name the loader resolves via
    ``importlib.util.find_spec``; ``dist`` (optional) supplies the
    extension_id/version stamped on discovered components.
    """

    def __init__(self, value: str, *, name: str = "lfx_bundles", dist: object | None = None) -> None:
        self.name = name
        self.value = value
        self.dist = dist
        self.group = LFX_BUNDLES_ENTRY_POINT_GROUP

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"_FakeBundlesEntryPoint(name={self.name!r}, value={self.value!r})"


def _make_provider(root: Path, name: str, *, class_name: str | None = None) -> Path:
    """Create one provider subdirectory with a single Component module."""
    provider = root / name
    provider.mkdir(parents=True, exist_ok=True)
    cls = class_name or f"{name.replace('_', ' ').title().replace(' ', '')}Thing"
    (provider / "thing.py").write_text(component_source(cls), encoding="utf-8")
    return provider


def _make_bundles_root(parent: Path, *provider_names: str, pkg: str = "lfx_bundles") -> Path:
    """Lay out a manifest-less metapackage tree: ``<pkg>/<provider>/thing.py``."""
    root = parent / pkg
    root.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name in provider_names:
        _make_provider(root, name)
    return root


def _component(bundle: str, class_name: str = "Thing") -> LoadedComponent:
    """A minimal @official LoadedComponent for resolver-level shadowing tests."""
    return LoadedComponent(
        extension_id=bundle,
        extension_version="1.0.0",
        bundle=bundle,
        class_name=class_name,
        slot=SLOT_OFFICIAL,
        klass=object,
        module_name=f"_synthetic.{bundle}.{class_name}",
        file_path=Path("synthetic") / bundle / "thing.py",
    )


# ---------------------------------------------------------------------------
# Folder-walk core: _load_bundle_roots
# ---------------------------------------------------------------------------


def test_root_registers_each_provider_at_official(tmp_path: Path) -> None:
    """Every immediate subdirectory becomes one @official bundle named after it."""
    root = _make_bundles_root(tmp_path, "alpha", "beta")

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0")])
    by_bundle = {r.bundle: r for r in results if r.bundle}

    assert set(by_bundle) == {"alpha", "beta"}
    for bundle, result in by_bundle.items():
        assert result.ok, [e.code for e in result.errors]
        assert result.slot == SLOT_OFFICIAL
        # Manifest-less records carry the providing-distribution identity for
        # display but no distribution (they are not the installed-manifest tier).
        assert result.distribution is None
        assert result.extension_id == "lfx-bundles"
        assert result.extension_version == "1.0.0"
        assert result.components
        for comp in result.components:
            assert comp.slot == SLOT_OFFICIAL
            assert comp.distribution is None
            assert comp.bundle == bundle
            assert comp.namespaced_id == f"ext:{bundle}:{comp.class_name}@official"


def test_invalid_provider_name_emits_malformed_warning_and_skips(tmp_path: Path) -> None:
    """A provider folder that is not lowercase snake_case is surfaced, not silently dropped."""
    root = _make_bundles_root(tmp_path, "good")
    _make_provider(root, "BadName")  # capitals fail BUNDLE_NAME_RE

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0")])

    loaded = {r.bundle for r in results if r.bundle and r.components}
    assert loaded == {"good"}  # the invalid one did not load
    malformed = [e for r in results for e in r.warnings if e.code == "bundle-discovery-malformed"]
    assert any(e.content == "BadName" for e in malformed)
    # The malformed entry produced no components.
    assert all(not r.components for r in results if any(w.content == "BadName" for w in r.warnings))


def test_internal_directories_skipped_silently(tmp_path: Path) -> None:
    """Dot/underscore-prefixed and __pycache__ dirs are package machinery, not bundles."""
    root = _make_bundles_root(tmp_path, "valid")
    (root / "_shared").mkdir()
    (root / "_shared" / "base.py").write_text("X = 1\n", encoding="utf-8")
    (root / ".hidden").mkdir()
    (root / "__pycache__").mkdir()

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0")])

    assert [r.bundle for r in results if r.bundle] == ["valid"]
    # No spurious warnings for the internal directories.
    assert not [e for r in results for e in r.warnings]


def test_duplicate_provider_across_roots_first_wins(tmp_path: Path) -> None:
    """Two roots shipping the same provider name: first wins, loser warns."""
    root_a = _make_bundles_root(tmp_path / "a", "dup", pkg="lfx_bundles")
    root_b = _make_bundles_root(tmp_path / "b", "dup", pkg="lfx_bundles_other")

    results = _load_bundle_roots(
        [
            _BundleRoot(root_a, "lfx-bundles", "1.0.0"),
            _BundleRoot(root_b, "lfx-bundles-other", "2.0.0"),
        ]
    )

    dup_results = [r for r in results if r.bundle == "dup"]
    with_components = [r for r in dup_results if r.components]
    shadowed = [r for r in dup_results if any(e.code == "bundle-shadowed" for e in r.warnings)]
    assert len(with_components) == 1  # exactly one winner
    assert len(shadowed) == 1  # exactly one shadowed loser
    assert not shadowed[0].components


# ---------------------------------------------------------------------------
# Entry-point resolution + malformed declarations
# ---------------------------------------------------------------------------


def test_unresolvable_declaration_warns_and_does_not_raise() -> None:
    """A declaration pointing at a non-existent module degrades to a warning."""
    roots, sentinels = _resolve_bundle_roots([_FakeBundlesEntryPoint("module_that_does_not_exist_xyz")])

    assert roots == []
    codes = [e.code for s in sentinels for e in s.warnings]
    assert codes == ["bundle-discovery-malformed"]
    # Warning-only: ok stays True, so a broken third-party declaration never
    # flips a startup gate.
    assert all(s.ok for s in sentinels)


def test_empty_entry_point_value_is_malformed() -> None:
    """An empty entry-point value is reported, not silently ignored."""
    roots, sentinels = _resolve_bundle_roots([_FakeBundlesEntryPoint("")])
    assert roots == []
    assert [e.code for s in sentinels for e in s.warnings] == ["bundle-discovery-malformed"]


def test_no_entry_points_is_empty_no_op() -> None:
    """Engine-only install (no distribution declares lfx.bundles) -> []."""
    assert load_lfx_bundles_extensions(entry_points=[]) == []


def test_end_to_end_real_package_resolution(tmp_path: Path, monkeypatch) -> None:
    """A real importable package on sys.path resolves and its providers load."""
    pkg_name = "lfx_bundles_e2e_fixture"
    _make_bundles_root(tmp_path, "gamma", "delta", pkg=pkg_name)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    try:
        results = load_lfx_bundles_extensions(entry_points=[_FakeBundlesEntryPoint(pkg_name)])
        by_bundle = {r.bundle: r for r in results if r.bundle and r.components}
        assert set(by_bundle) == {"gamma", "delta"}
        for result in by_bundle.values():
            assert result.slot == SLOT_OFFICIAL
            assert result.ok, [e.code for e in result.errors]
    finally:
        importlib.invalidate_caches()


# ---------------------------------------------------------------------------
# Cross-source precedence: manifest shadows manifest-less (the graduation property)
# ---------------------------------------------------------------------------


def test_installed_manifest_shadows_manifest_less_provider() -> None:
    """A graduated lfx-<provider> (installed manifest) wins over the same name in lfx-bundles."""
    installed = LoadResult(
        slot=SLOT_OFFICIAL,
        source_path=Path("/install/lfx_openai"),
        distribution="lfx-openai",
        bundle="openai",
        components=[_component("openai")],
    )
    metapackage = LoadResult(
        slot=SLOT_OFFICIAL,
        source_path=Path("/install/lfx_bundles/openai"),
        distribution=None,
        bundle="openai",
        components=[_component("openai")],
    )

    _resolve_bundle_shadowing(
        extension_results=[installed],
        seed_results=[],
        lfx_bundles_results=[metapackage],
        dev_results=[],
        inline_results=[],
    )

    # Installed manifest keeps its components; the manifest-less copy is dropped
    # with a typed bundle-shadowed warning.
    assert installed.components
    assert metapackage.components == []
    assert any(e.code == "bundle-shadowed" for e in metapackage.errors)


def test_manifest_less_shadows_loose_inline_source() -> None:
    """lfx-bundles sits above the loose dev/inline sources in precedence."""
    metapackage = LoadResult(
        slot=SLOT_OFFICIAL,
        source_path=Path("/install/lfx_bundles/tavily"),
        distribution=None,
        bundle="tavily",
        components=[_component("tavily")],
    )
    inline = LoadResult(
        slot="extra",
        source_path=Path("/loose/tavily"),
        distribution=None,
        bundle="tavily",
        components=[_component("tavily")],
    )

    _resolve_bundle_shadowing(
        extension_results=[],
        seed_results=[],
        lfx_bundles_results=[metapackage],
        dev_results=[],
        inline_results=[inline],
    )

    assert metapackage.components  # higher precedence wins
    assert inline.components == []
    assert any(e.code == "bundle-shadowed" for e in inline.errors)
