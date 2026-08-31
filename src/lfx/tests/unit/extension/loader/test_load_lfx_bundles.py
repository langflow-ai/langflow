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
import sys
from pathlib import Path
from types import SimpleNamespace

from lfx.extension import SLOT_OFFICIAL, LoadedComponent, LoadResult, load_lfx_bundles_extensions
from lfx.extension.loader._bundles_root import (
    LFX_BUNDLES_ENTRY_POINT_GROUP,
    _BundleRoot,
    _load_bundle_roots,
    _optional_dependency_distributions,
    _resolve_bundle_roots,
)
from lfx.extension.loader._orchestrator import _load_bundle_directory
from lfx.interface.components import _claimed_official_bundles, _emit_extension_diagnostics, _resolve_bundle_shadowing

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


def test_mrscraper_provider_loads_with_production_bundle_loader(monkeypatch) -> None:
    """The checked-in MrScraper provider registers all components at @official."""
    repo_root = Path(__file__).resolve().parents[6]
    bundles_source = repo_root / "src" / "bundles" / "lfx-bundles" / "src"
    provider = bundles_source / "lfx_bundles" / "mrscraper"
    result = LoadResult(
        slot=SLOT_OFFICIAL,
        source_path=provider,
        bundle="mrscraper",
        extension_id="lfx-bundles",
        extension_version="1.0.0",
        manifestless=True,
    )
    module_prefixes = ("_lfx_ext.official.mrscraper", "lfx_bundles")
    prior_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "lfx_bundles" or name.startswith(tuple(f"{prefix}." for prefix in module_prefixes))
    }
    for name in prior_modules:
        sys.modules.pop(name, None)

    monkeypatch.syspath_prepend(str(bundles_source))
    importlib.invalidate_caches()
    try:
        _load_bundle_directory(
            bundle_root=provider,
            bundle_name="mrscraper",
            extension_id="lfx-bundles",
            extension_version="1.0.0",
            slot=SLOT_OFFICIAL,
            distribution=None,
            result=result,
        )
    finally:
        for name in list(sys.modules):
            if name == "lfx_bundles" or name.startswith(tuple(f"{prefix}." for prefix in module_prefixes)):
                sys.modules.pop(name, None)
        sys.modules.update(prior_modules)
        importlib.invalidate_caches()

    assert result.ok, [(error.code, error.message) for error in result.errors]
    assert {component.class_name for component in result.components} == {
        "MrscraperAiScraper",
        "MrscraperBatchScrape",
        "MrscraperCrawlWebsite",
        "MrscraperFetchHtml",
        "MrscraperGetResult",
        "MrscraperGetResults",
        "MrscraperRunAiScraper",
        "MrscraperRunManualScraper",
    }


def test_invalid_provider_name_emits_typed_warning_and_skips(tmp_path: Path) -> None:
    """A provider folder that is not lowercase snake_case is surfaced, not silently dropped.

    Dedicated code (not ``bundle-discovery-malformed``): the fix is renaming
    the directory, not editing the entry-point declaration, and the rendered
    template/hint must say so.
    """
    root = _make_bundles_root(tmp_path, "good")
    _make_provider(root, "BadName")  # capitals fail BUNDLE_NAME_RE

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0")])

    loaded = {r.bundle for r in results if r.bundle and r.components}
    assert loaded == {"good"}  # the invalid one did not load
    invalid = [e for r in results for e in r.warnings if e.code == "bundles-provider-name-invalid"]
    assert any(e.content == "BadName" for e in invalid)
    # The invalid entry produced no components.
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


def test_symlinked_provider_escaping_root_is_skipped(tmp_path: Path) -> None:
    """A provider dir symlinked outside the bundle root is rejected, not loaded.

    Mirrors the seed-directory walk's containment rule: the trust boundary is
    the installed package tree, so a symlink pointing elsewhere (e.g. into an
    operator's filesystem) must not be folder-walked and imported.
    """
    outside = tmp_path / "outside" / "evil"
    outside.mkdir(parents=True)
    (outside / "thing.py").write_text(component_source("EvilThing"), encoding="utf-8")

    root = _make_bundles_root(tmp_path, "good")
    (root / "escapee").symlink_to(outside, target_is_directory=True)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0")])

    loaded = {r.bundle for r in results if r.bundle and r.components}
    assert loaded == {"good"}  # the symlinked-out provider did not load
    escapes = [e for r in results for e in r.warnings if e.code == "path-escape"]
    assert any(e.content == "escapee" and "outside the bundle root" in e.message for e in escapes)


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
    # Same-tier duplicate carries its own code -- ``bundle-shadowed`` means
    # cross-source precedence and would render a misleading template here.
    shadowed = [r for r in dup_results if any(e.code == "duplicate-lfx-bundles-provider" for e in r.warnings)]
    assert len(with_components) == 1  # exactly one winner
    assert len(shadowed) == 1  # exactly one shadowed loser
    assert not shadowed[0].components


def test_claimed_bundle_name_is_not_imported(tmp_path: Path) -> None:
    """A name won by an installed/seed source is skipped *without importing*.

    All @official sources share the ``_lfx_ext.official.<bundle>.*``
    sys.modules namespace; importing the metapackage's losing copy would
    overwrite the winner's live modules even though shadow resolution drops
    the loser's components afterwards.  This is the expected post-graduation
    state (standalone ``lfx-<provider>`` next to an older metapackage).
    """
    root = _make_bundles_root(tmp_path, "claimedprov", "freeprov")

    results = _load_bundle_roots(
        [_BundleRoot(root, "lfx-bundles", "1.0.0")],
        claimed_bundles={"claimedprov": ("installed", "/site-packages/lfx_claimedprov")},
    )
    by_bundle = {r.bundle: r for r in results if r.bundle}

    assert set(by_bundle) == {"claimedprov", "freeprov"}
    claimed = by_bundle["claimedprov"]
    assert not claimed.components
    # Same code AND same severity as _resolve_bundle_shadowing emits
    # for every other cross-source shadow pair.
    assert [e.code for e in claimed.warnings] == ["bundle-shadowed"]
    assert "installed" in claimed.warnings[0].message
    assert claimed.ok
    # The decisive property: nothing was imported for the claimed name, so
    # the winner's live modules cannot have been overwritten.
    assert not [k for k in sys.modules if k.startswith("_lfx_ext.official.claimedprov")]
    # The unclaimed sibling in the same root still loads normally.
    assert by_bundle["freeprov"].components


def test_provider_results_are_marked_manifestless(tmp_path: Path) -> None:
    """Provider results carry the provenance flag the reload pipeline keys on."""
    root = _make_bundles_root(tmp_path, "flagged")

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0")])

    assert results
    assert all(r.manifestless for r in results if r.bundle)


def test_declared_optional_dependency_missing_is_warning_only(tmp_path: Path) -> None:
    """A missing dependency declared by this provider extra does not fail startup."""
    root = _make_bundles_root(tmp_path, "composio")
    (root / "composio" / "thing.py").write_text("import composio_missing_fixture\n", encoding="utf-8")
    requirements = ('composio-missing-fixture>=1; extra == "composio"',)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0", requirements)])

    result = next(item for item in results if item.bundle == "composio")
    assert result.ok
    assert not result.errors
    assert [warning.code for warning in result.warnings] == ["optional-dependency-missing"]
    assert result.warnings[0].content == "composio_missing_fixture"


def test_undeclared_missing_dependency_remains_error(tmp_path: Path) -> None:
    """Manifest-less code cannot downgrade an undeclared import failure."""
    root = _make_bundles_root(tmp_path, "composio")
    (root / "composio" / "thing.py").write_text("import unrelated_missing_fixture\n", encoding="utf-8")
    requirements = ('composio>=1; extra == "composio"',)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0", requirements)])

    result = next(item for item in results if item.bundle == "composio")
    assert not result.ok
    assert [error.code for error in result.errors] == ["module-import-failed"]
    assert not result.warnings


def test_only_module_not_found_is_downgraded_for_manifestless_bundle(tmp_path: Path) -> None:
    """ImportError, syntax failures, and runtime failures stay hard errors."""
    root = _make_bundles_root(tmp_path, "composio")
    provider = root / "composio"
    (provider / "import_error.py").write_text("raise ImportError('missing symbol')\n", encoding="utf-8")
    (provider / "syntax_error.py").write_text("if:\n", encoding="utf-8")
    (provider / "runtime_error.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    requirements = ('composio>=1; extra == "composio"',)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0", requirements)])

    result = next(item for item in results if item.bundle == "composio")
    assert [error.code for error in result.errors] == ["module-import-failed"] * 3
    assert not [warning for warning in result.warnings if warning.code == "optional-dependency-missing"]


def test_declared_missing_dependency_stays_error_outside_manifestless_tier(tmp_path: Path) -> None:
    """Installed, seed, dev, and inline loaders cannot opt into this downgrade."""
    provider = tmp_path / "composio"
    provider.mkdir()
    (provider / "thing.py").write_text("import composio_missing_fixture\n", encoding="utf-8")
    result = LoadResult(slot=SLOT_OFFICIAL, source_path=provider, bundle="composio", manifestless=False)

    _load_bundle_directory(
        bundle_root=provider,
        bundle_name="composio",
        extension_id="lfx-composio",
        extension_version="1.0.0",
        slot=SLOT_OFFICIAL,
        distribution="lfx-composio",
        result=result,
        optional_dependency_distributions={"composiomissingfixture": "composio-missing-fixture"},
    )

    assert [error.code for error in result.errors] == ["module-import-failed"]
    assert not result.warnings


def test_optional_dependency_distributions_come_from_matching_extra_metadata() -> None:
    requirements = (
        'langchain-mistralai>=1; extra == "mistral"',
        'opensearch-py>=2; extra == "elastic"',
        'unrelated>=1; extra == "other"',
    )

    mistral_distributions = _optional_dependency_distributions(requirements, bundle_name="mistral")
    assert mistral_distributions == {"langchainmistralai": "langchain-mistralai"}
    elastic_distributions = _optional_dependency_distributions(requirements, bundle_name="elastic")
    assert elastic_distributions == {"opensearchpy": "opensearch-py"}


def test_shared_lfx_namespace_failure_remains_error(tmp_path: Path) -> None:
    """A declared lfx-* distribution cannot downgrade arbitrary lfx.* failures."""
    root = _make_bundles_root(tmp_path, "openai")
    (root / "openai" / "thing.py").write_text("import lfx.missing_optional_fixture\n", encoding="utf-8")
    requirements = ('lfx-openai>=1; extra == "openai"',)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0", requirements)])

    result = next(item for item in results if item.bundle == "openai")
    assert [error.code for error in result.errors] == ["module-import-failed"]
    assert not result.warnings


def test_shared_langchain_namespace_failure_remains_error(tmp_path: Path) -> None:
    """A declared langchain-* distribution cannot downgrade arbitrary langchain.* failures."""
    root = _make_bundles_root(tmp_path, "mistral")
    (root / "mistral" / "thing.py").write_text("import langchain.missing_optional_fixture\n", encoding="utf-8")
    requirements = ('langchain-mistralai>=1; extra == "mistral"',)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0", requirements)])

    result = next(item for item in results if item.bundle == "mistral")
    assert [error.code for error in result.errors] == ["module-import-failed"]
    assert not result.warnings


def test_installed_but_broken_optional_dependency_remains_error(tmp_path: Path) -> None:
    """Metadata presence proves the dependency is installed, so a broken import stays hard."""
    root = _make_bundles_root(tmp_path, "packaging_provider")
    (root / "packaging_provider" / "thing.py").write_text(
        "import packaging.missing_optional_fixture\n", encoding="utf-8"
    )
    requirements = ('packaging>=1; extra == "packaging-provider"',)

    results = _load_bundle_roots([_BundleRoot(root, "lfx-bundles", "1.0.0", requirements)])

    result = next(item for item in results if item.bundle == "packaging_provider")
    assert [error.code for error in result.errors] == ["module-import-failed"]
    assert not result.warnings


def test_entry_point_distribution_metadata_drives_optional_warning(tmp_path: Path, monkeypatch) -> None:
    """The production entry-point path carries Requires-Dist into provider loading."""
    package_name = "lfx_bundles_optional_metadata_fixture"
    root = _make_bundles_root(tmp_path, "composio", pkg=package_name)
    (root / "composio" / "thing.py").write_text("import composio_missing_fixture\n", encoding="utf-8")
    distribution = SimpleNamespace(
        name="lfx-bundles",
        version="1.0.0",
        requires=['composio-missing-fixture>=1; extra == "composio"'],
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    try:
        results = load_lfx_bundles_extensions(entry_points=[_FakeBundlesEntryPoint(package_name, dist=distribution)])
    finally:
        importlib.invalidate_caches()

    result = next(item for item in results if item.bundle == "composio")
    assert result.ok
    assert [warning.code for warning in result.warnings] == ["optional-dependency-missing"]


def test_optional_dependency_diagnostics_are_aggregated(monkeypatch, tmp_path: Path) -> None:
    """Repeated missing imports produce one operator warning plus debug details."""
    from lfx.extension.errors import ExtensionError
    from lfx.interface import components as components_module

    missing_modules = ("composio.foo", "composio.bar", "composio")
    results = []
    for index, missing_module in enumerate(missing_modules):
        result = LoadResult(bundle="composio", manifestless=True)
        result.warnings.append(
            ExtensionError(
                code="optional-dependency-missing",
                message="ModuleNotFoundError: optional dependency is not installed.",
                location=str(tmp_path / f"module_{index}.py"),
                content=missing_module,
                hint="Install lfx-bundles[composio].",
            )
        )
        results.append(result)
    warning_calls = []
    debug_calls = []
    monkeypatch.setattr(components_module.logger, "warning", lambda *args: warning_calls.append(args))
    monkeypatch.setattr(components_module.logger, "debug", lambda *args: debug_calls.append(args))

    _emit_extension_diagnostics(results)

    assert len(warning_calls) == 1
    assert warning_calls[0][2] == "composio"
    assert warning_calls[0][3] == 3
    assert str(tmp_path / "module_0.py") == warning_calls[0][4]
    assert len(debug_calls) == 3


def test_claimed_official_bundles_first_wins_and_requires_components(tmp_path: Path) -> None:
    """The claim map mirrors the resolver's winner rule.

    Only results that produced components claim a name, and the
    highest-precedence claimant (installed before seed) wins.
    """
    installed_alpha = LoadResult(
        slot=SLOT_OFFICIAL,
        bundle="alpha",
        source_path=tmp_path / "inst" / "alpha",
        components=[_component("alpha")],
    )
    seed_alpha = LoadResult(
        slot=SLOT_OFFICIAL,
        bundle="alpha",
        source_path=tmp_path / "seed" / "alpha",
        components=[_component("alpha")],
    )
    seed_empty = LoadResult(slot=SLOT_OFFICIAL, bundle="empty", source_path=tmp_path / "seed" / "empty")

    claimed = _claimed_official_bundles([installed_alpha], [seed_alpha, seed_empty])

    assert claimed == {"alpha": ("installed", str(tmp_path / "inst" / "alpha"))}


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


def test_raising_parent_package_degrades_to_malformed(tmp_path: Path, monkeypatch) -> None:
    """A dotted declaration whose parent package raises on import never escapes.

    ``find_spec("pkg.sub")`` imports ``pkg`` -- arbitrary third-party
    ``__init__`` code that can raise anything, not just ImportError.  An
    escape here would reach the palette cache's catch-all and wipe EVERY
    source's components for the boot; instead it degrades to one malformed
    sentinel and the rest of discovery proceeds.
    """
    pkg = tmp_path / "rottenpkg_fixture"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    (pkg / "bundles").mkdir()
    (pkg / "bundles" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    try:
        roots, sentinels = _resolve_bundle_roots([_FakeBundlesEntryPoint("rottenpkg_fixture.bundles")])
        assert roots == []
        assert [e.code for s in sentinels for e in s.warnings] == ["bundle-discovery-malformed"]
        assert "RuntimeError" in sentinels[0].warnings[0].message
        assert all(s.ok for s in sentinels)
    finally:
        sys.modules.pop("rottenpkg_fixture", None)
        importlib.invalidate_caches()


def test_namespace_package_portions_are_all_walked(tmp_path: Path, monkeypatch) -> None:
    """Every portion of a namespace package contributes providers.

    A namespace package split across two sys.path entries has one
    ``submodule_search_locations`` entry per portion; walking only the first
    would silently drop the other portion's providers (with the winner
    decided by sys.path order).
    """
    pkg = "ns_bundles_fixture"
    for portion, provider in (("a", "portiona_prov"), ("b", "portionb_prov")):
        root = tmp_path / portion / pkg
        root.mkdir(parents=True)  # deliberately no __init__.py: namespace portions
        _make_provider(root, provider)
        monkeypatch.syspath_prepend(str(tmp_path / portion))
    importlib.invalidate_caches()
    try:
        results = load_lfx_bundles_extensions(entry_points=[_FakeBundlesEntryPoint(pkg)])
        loaded = {r.bundle for r in results if r.bundle and r.components}
        assert loaded == {"portiona_prov", "portionb_prov"}
        assert not [e for r in results for e in (*r.warnings, *r.errors)]
    finally:
        importlib.invalidate_caches()


def test_duplicate_entry_points_walk_the_root_once(tmp_path: Path, monkeypatch) -> None:
    """Two declarations naming the same package do not walk its directory twice.

    Without path-level dedupe the second walk would make every provider in
    the root shadow-warn against itself.
    """
    pkg = "dup_ep_bundles_fixture"
    _make_bundles_root(tmp_path, "dupepprov", pkg=pkg)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    try:
        results = load_lfx_bundles_extensions(
            entry_points=[
                _FakeBundlesEntryPoint(pkg, name="first"),
                _FakeBundlesEntryPoint(pkg, name="second"),
            ]
        )
        dup = [r for r in results if r.bundle == "dupepprov"]
        assert len(dup) == 1
        assert dup[0].components
        assert not [e for r in results for e in (*r.warnings, *r.errors)]
    finally:
        importlib.invalidate_caches()


def test_plain_module_entry_point_is_malformed_not_scanned(tmp_path: Path, monkeypatch) -> None:
    """A declaration pointing at a single-file module is malformed, not a root.

    A plain module has no provider subdirectories; treating its parent
    directory as a bundle root would folder-walk unrelated siblings (here a
    provider-shaped directory next to the module file).
    """
    module_name = "lfx_bundles_plain_module_fixture"
    (tmp_path / f"{module_name}.py").write_text("", encoding="utf-8")
    _make_provider(tmp_path, "sneaky_sibling")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    try:
        roots, sentinels = _resolve_bundle_roots([_FakeBundlesEntryPoint(module_name)])
        assert roots == []
        assert [e.code for s in sentinels for e in s.warnings] == ["bundle-discovery-malformed"]
        assert all(s.ok for s in sentinels)
    finally:
        importlib.invalidate_caches()


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
    assert any(e.code == "bundle-shadowed" for e in metapackage.warnings)
    assert metapackage.ok


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
    assert any(e.code == "bundle-shadowed" for e in inline.warnings)
    assert inline.ok
