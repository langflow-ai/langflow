"""Tests for ``lfx.extension.loader`` (LE-1015).

Coverage targets from the ticket:
    - single-Bundle shorthand and one manifest-declared Bundle path,
    - multi-Bundle rejection (``multi-bundle-deferred-in-this-milestone``),
    - missing build() detection at AST time is owned by validate; here we
      cover loader-side behavior: duplicate component class names within
      a bundle, modules that fail to import, bundles with no Component
      subclass, bundles with no .py files,
    - LANGFLOW_COMPONENTS_PATH walk: deterministic order, first-wins on
      same-named bundles, ``duplicate-inline-bundle`` warning carries both
      paths, invalid bundle names emit a typed error,
    - manifest-first precedence: a distribution that ships a manifest is
      filtered out of the legacy ``langflow.plugins`` entry-point set,
      while non-component entry-points on other distributions are kept.

Synthetic bundles in these tests use a tiny inline ``Component`` base class
defined in the bundle itself so the loader can verify subclass detection
without dragging in the real lfx Component (which requires the full graph
stack and is irrelevant to registration semantics).
"""

from __future__ import annotations

import json
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from lfx.extension import (
    SLOT_EXTRA,
    SLOT_OFFICIAL,
    LoadedComponent,
    LoadResult,
    discover_inline_bundles,
    filter_plugin_entry_points,
    installed_extension_roots,
    load_extension,
    manifest_owning_distributions,
)
from lfx.extension.loader import _canonicalize_distribution

if TYPE_CHECKING:
    from collections.abc import Iterable


_BASE_MANIFEST: dict = {
    "id": "lfx-pilot",
    "version": "1.2.3",
    "name": "Pilot Bundle",
    "lfx": {"compat": ["1"]},
    "bundles": [{"name": "pilot", "path": "components"}],
}


def _component_source(class_name: str = "PilotThing", *, with_build: bool = True) -> str:
    """Return source text for a minimal Component subclass.

    The bundle defines its own toy ``Component`` base so the loader's
    subclass check fires without importing the real lfx Component.
    """
    body = "    def build(self):\n        return None\n" if with_build else "    pass\n"
    return f"class Component:\n    pass\n\nclass {class_name}(Component):\n    display_name = 'X'\n{body}"


def _make_extension(
    tmp_path: Path,
    *,
    manifest: dict | None = None,
    files: dict[str, str] | None = None,
) -> Path:
    """Lay out a synthetic extension at ``tmp_path``."""
    manifest = manifest if manifest is not None else _BASE_MANIFEST
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle_dir = tmp_path / manifest["bundles"][0]["path"]
    bundle_dir.mkdir(parents=True, exist_ok=True)
    files = files if files is not None else {"thing.py": _component_source()}
    for name, source in files.items():
        target = bundle_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def _scrub_synthetic_modules() -> Iterable[None]:
    """Ensure tests don't leak imported modules across runs.

    The loader installs each bundle module under ``_lfx_ext.<slot>...`` so
    intra-bundle relative imports work; we strip those after every test so
    a later test's identically-named module gets re-imported clean.
    """
    yield
    for name in [m for m in sys.modules if m.startswith("_lfx_ext.")]:
        sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# load_extension: happy path + identity tuple
# ---------------------------------------------------------------------------


def test_load_extension_single_bundle_registers_component(tmp_path: Path) -> None:
    root = _make_extension(tmp_path)
    result = load_extension(root)
    assert result.ok, result.errors
    assert result.extension_id == "lfx-pilot"
    assert result.extension_version == "1.2.3"
    assert result.bundle == "pilot"
    assert result.slot == SLOT_OFFICIAL
    assert len(result.components) == 1
    component = result.components[0]
    assert isinstance(component, LoadedComponent)
    assert component.class_name == "PilotThing"
    assert component.namespaced_id == "ext:pilot:PilotThing@official"
    assert component.extension_version == "1.2.3"
    assert component.distribution is None


def test_load_extension_components_path_shorthand(tmp_path: Path) -> None:
    """Manifest with bundle path = ``./components/`` (the recommended layout)."""
    manifest = {**_BASE_MANIFEST, "bundles": [{"name": "pilot", "path": "components"}]}
    root = _make_extension(tmp_path, manifest=manifest)
    result = load_extension(root)
    assert result.ok, result.errors
    assert result.components[0].file_path.parent.name == "components"


def test_load_extension_alternate_bundle_path(tmp_path: Path) -> None:
    """Manifest pointing at a non-``components/`` directory still works."""
    manifest = {**_BASE_MANIFEST, "bundles": [{"name": "pilot", "path": "src/pilot"}]}
    root = _make_extension(tmp_path, manifest=manifest)
    result = load_extension(root)
    assert result.ok, result.errors
    assert result.components[0].file_path.parent.name == "pilot"


def test_load_extension_passes_distribution_through(tmp_path: Path) -> None:
    root = _make_extension(tmp_path)
    result = load_extension(root, distribution="lfx-pilot")
    assert result.ok
    assert result.components[0].distribution == "lfx-pilot"
    assert result.distribution == "lfx-pilot"


# ---------------------------------------------------------------------------
# load_extension: failure paths
# ---------------------------------------------------------------------------


def test_load_extension_missing_manifest(tmp_path: Path) -> None:
    result = load_extension(tmp_path)
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert codes == ["manifest-not-found"]
    # AC: fix-hint payload is present on failure.
    assert result.errors[0].hint
    assert result.errors[0].ref_url


def test_load_extension_rejects_multi_bundle_at_load_time(tmp_path: Path) -> None:
    """The schema rejects multi-bundle, but the loader re-checks at runtime.

    To exercise the runtime gate, we bypass the manifest schema by stubbing
    a pre-built ExtensionManifest -- but that's harder than necessary.
    Instead, this test confirms the schema-side rejection produces a
    ``manifest-invalid`` error wrapped at the loader boundary; the dedicated
    code (``multi-bundle-deferred-in-this-milestone``) is exercised by the
    validator's test suite and re-checked structurally below.
    """
    multi = {**_BASE_MANIFEST, "bundles": [{"name": "a", "path": "a"}, {"name": "b", "path": "b"}]}
    (tmp_path / "extension.json").write_text(json.dumps(multi), encoding="utf-8")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    result = load_extension(tmp_path)
    assert not result.ok
    # Schema layer returns ValueError, mapped to manifest-invalid by the loader.
    assert result.errors[0].code == "manifest-invalid"


def test_load_extension_runtime_multi_bundle_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Loader-side multi-bundle guard.

    Even if a forged manifest somehow bypassed the schema, the loader still
    rejects with the dedicated ``multi-bundle-deferred-in-this-milestone`` code.
    """
    from lfx.extension import loader as loader_mod
    from lfx.extension.manifest import (
        BundleRef,
        ExtensionManifest,
        LfxCompat,
        ManifestSource,
    )

    bundle_a = tmp_path / "alpha"
    bundle_a.mkdir()
    bundle_b = tmp_path / "bravo"
    bundle_b.mkdir()
    (tmp_path / "extension.json").write_text("{}", encoding="utf-8")  # placeholder

    # Build a manifest that bypasses the post-init validator via
    # ``model_construct``; this models a forged on-disk manifest reaching
    # the loader without re-validation.
    forged = ExtensionManifest.model_construct(
        id="lfx-pilot",
        version="1.2.3",
        name="Pilot",
        lfx=LfxCompat(compat=["1"]),
        bundles=[BundleRef(name="alpha", path="alpha"), BundleRef(name="bravo", path="bravo")],
    )
    source = ManifestSource.model_construct(manifest=forged, path=tmp_path / "extension.json", kind="extension.json")

    def fake_load_manifest(_root: Path) -> ManifestSource:
        return source

    monkeypatch.setattr(loader_mod, "load_manifest", fake_load_manifest)
    result = load_extension(tmp_path)
    codes = [e.code for e in result.errors]
    assert codes == ["multi-bundle-deferred-in-this-milestone"]


def test_load_extension_missing_bundle_directory(tmp_path: Path) -> None:
    manifest = {**_BASE_MANIFEST, "bundles": [{"name": "pilot", "path": "missing"}]}
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = load_extension(tmp_path)
    codes = [e.code for e in result.errors]
    assert codes == ["bundle-path-not-found"]


def test_load_extension_empty_bundle(tmp_path: Path) -> None:
    root = _make_extension(tmp_path, files={})  # no .py files
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert codes == ["bundle-empty"]


def test_load_extension_no_component_subclass(tmp_path: Path) -> None:
    root = _make_extension(tmp_path, files={"plain.py": "x = 1\n"})
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert codes == ["no-component-subclass"]


def test_load_extension_module_import_failure(tmp_path: Path) -> None:
    root = _make_extension(tmp_path, files={"broken.py": "raise RuntimeError('boom at import')\n"})
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert "module-import-failed" in codes
    failure = next(e for e in result.errors if e.code == "module-import-failed")
    assert "boom at import" in failure.message
    # Identity is still attributed even on partial failure (AC: fix-hint payload).
    assert result.extension_id == "lfx-pilot"


def test_load_extension_duplicate_component_name(tmp_path: Path) -> None:
    files = {
        "first.py": _component_source("PilotThing"),
        "second.py": _component_source("PilotThing"),
    }
    root = _make_extension(tmp_path, files=files)
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert "duplicate-component-name" in codes
    # First-seen component still registers; only the duplicate is rejected.
    classes = [c.class_name for c in result.components]
    assert classes.count("PilotThing") == 1


def test_load_extension_skips_init_and_dunder_files(tmp_path: Path) -> None:
    files = {
        "__init__.py": "",  # skipped
        "__main__.py": "raise SystemExit\n",  # skipped (would crash if executed)
        "thing.py": _component_source(),
    }
    root = _make_extension(tmp_path, files=files)
    result = load_extension(root)
    assert result.ok, result.errors
    assert {c.class_name for c in result.components} == {"PilotThing"}


def test_load_extension_recurses_subdirectories(tmp_path: Path) -> None:
    files = {
        "a.py": _component_source("Alpha"),
        "nested/b.py": _component_source("Bravo"),
        "nested/deep/c.py": _component_source("Charlie"),
    }
    root = _make_extension(tmp_path, files=files)
    result = load_extension(root)
    assert result.ok, result.errors
    assert {c.class_name for c in result.components} == {"Alpha", "Bravo", "Charlie"}


def test_load_extension_component_order_is_deterministic(tmp_path: Path) -> None:
    files = {
        "z.py": _component_source("Zeta"),
        "a.py": _component_source("Alpha"),
        "m.py": _component_source("Mike"),
    }
    root = _make_extension(tmp_path, files=files)
    result_first = load_extension(root)
    # Loading the same extension twice yields the same order.
    result_second = load_extension(root)
    names_first = [c.class_name for c in result_first.components]
    names_second = [c.class_name for c in result_second.components]
    assert names_first == names_second
    assert names_first == ["Alpha", "Mike", "Zeta"]


def test_load_extension_skips_re_imported_class(tmp_path: Path) -> None:
    """A class imported (not declared) in another module shouldn't double-register."""
    files = {
        "primary.py": _component_source("Primary"),
        # Re-export -- the loader should skip the imported class because its
        # __module__ does not match this file's synthetic module name.
        "alias.py": "from .primary import Primary  # noqa: F401\n",
    }
    root = _make_extension(tmp_path, files=files)
    result = load_extension(root)
    # The alias module's relative import will fail because the synthetic
    # module package isn't a real package; that's an expected import-time
    # error. The primary class should still register.
    primary_names = [c.class_name for c in result.components if c.class_name == "Primary"]
    assert len(primary_names) == 1


# ---------------------------------------------------------------------------
# Inline bundles via LANGFLOW_COMPONENTS_PATH (@extra slot)
# ---------------------------------------------------------------------------


def _make_inline_bundle(parent: Path, name: str, files: dict[str, str] | None = None) -> Path:
    bundle_dir = parent / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    files = files if files is not None else {"thing.py": _component_source(f"{name.capitalize()}Thing")}
    for fname, source in files.items():
        target = bundle_dir / fname
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return bundle_dir


def test_inline_bundles_loaded_from_subdirectories(tmp_path: Path) -> None:
    parent = tmp_path / "components_path"
    parent.mkdir()
    _make_inline_bundle(parent, "alpha")
    _make_inline_bundle(parent, "bravo")

    results = discover_inline_bundles([parent])
    assert len(results) == 2
    by_name = {r.bundle: r for r in results}
    assert {"alpha", "bravo"} == set(by_name)
    assert all(r.slot == SLOT_EXTRA for r in results)
    alpha = by_name["alpha"]
    assert alpha.ok
    assert alpha.components[0].namespaced_id == "ext:alpha:AlphaThing@extra"
    assert alpha.components[0].distribution is None
    # Default version when bundle.json is absent.
    assert alpha.extension_version == "0.0.0"


def test_inline_bundles_walk_order_is_lexicographic(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    _make_inline_bundle(parent, "zeta")
    _make_inline_bundle(parent, "alpha")
    _make_inline_bundle(parent, "mike")
    results = discover_inline_bundles([parent])
    names = [r.bundle for r in results]
    assert names == ["alpha", "mike", "zeta"]


def test_inline_bundles_first_wins_emits_duplicate_warning(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_inline_bundle(first, "shared")
    _make_inline_bundle(second, "shared")

    # Path order is significant: ``first`` declared first wins.
    results = discover_inline_bundles([first, second])
    assert len(results) == 2

    winning = next(r for r in results if r.ok and r.components)
    skipped = next(r for r in results if not r.ok or r.warnings)
    assert winning.source_path == (first / "shared").resolve()
    # The skipped result carries the typed warning with both paths in location.
    assert any(w.code == "duplicate-inline-bundle" for w in skipped.warnings)
    warning = next(w for w in skipped.warnings if w.code == "duplicate-inline-bundle")
    assert str(first / "shared") in warning.location
    assert str(second / "shared") in warning.location


def test_inline_bundles_invalid_directory_name_emits_typed_error(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    _make_inline_bundle(parent, "BadName")  # uppercase -> invalid pattern
    results = discover_inline_bundles([parent])
    assert len(results) == 1
    assert results[0].errors
    assert results[0].errors[0].code == "inline-bundle-name-invalid"


def test_inline_bundles_skips_dot_directories(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    _make_inline_bundle(parent, ".hidden")
    _make_inline_bundle(parent, "real")
    results = discover_inline_bundles([parent])
    assert [r.bundle for r in results] == ["real"]


def test_inline_bundles_respect_bundle_json(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    bundle_dir = _make_inline_bundle(parent, "alpha")
    (bundle_dir / "bundle.json").write_text(json.dumps({"id": "lfx-alpha", "version": "9.9.9"}), encoding="utf-8")
    results = discover_inline_bundles([parent])
    assert results[0].extension_id == "lfx-alpha"
    assert results[0].extension_version == "9.9.9"


def test_inline_bundles_handles_none_paths() -> None:
    assert discover_inline_bundles(None) == []


def test_inline_bundles_skips_non_existent_path(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    results = discover_inline_bundles([bogus])
    assert results == []


# ---------------------------------------------------------------------------
# Manifest-first precedence over langflow.plugins entry-points
# ---------------------------------------------------------------------------


class _FakeDist:
    """Minimal stand-in for ``importlib.metadata.Distribution``.

    Only the surface used by the loader is implemented: ``files``,
    ``locate_file``, ``metadata``.
    """

    def __init__(self, name: str, root: Path, files: list[Path] | None = None) -> None:
        self._name = name
        self._root = root
        self._files = files

    @property
    def files(self) -> list[Path] | None:
        return self._files

    def locate_file(self, path: Path) -> Path:
        return self._root / path

    @property
    def metadata(self) -> dict[str, str]:
        return {"Name": self._name}


class _FakeEntryPoint:
    def __init__(self, name: str, dist: _FakeDist | None) -> None:
        self.name = name
        self.dist = dist


def _make_installed_extension(parent: Path, distribution_name: str) -> _FakeDist:
    """Create a fake installed extension distribution.

    The distribution's ``files`` list points at a real ``extension.json`` so
    ``locate_file`` returns an existing path, exactly the contract that
    ``installed_extension_roots`` consumes.
    """
    pkg_dir = parent / distribution_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": distribution_name,
        "version": "1.0.0",
        "name": distribution_name,
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": distribution_name.replace("-", "_"), "path": "components"}],
    }
    manifest_file = pkg_dir / "extension.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    return _FakeDist(
        name=distribution_name,
        root=parent,
        files=[Path(distribution_name) / "extension.json"],
    )


def test_installed_extension_roots_finds_manifest_shipping_distribution(tmp_path: Path) -> None:
    dist = _make_installed_extension(tmp_path, "lfx-pilot")
    roots = installed_extension_roots(distributions=[dist])
    assert "lfx-pilot" in roots
    assert (roots["lfx-pilot"] / "extension.json").is_file()


def test_installed_extension_roots_canonicalizes_name(tmp_path: Path) -> None:
    """PEP-503: ``Lfx_Pilot`` and ``lfx-pilot`` are the same distribution."""
    dist = _make_installed_extension(tmp_path, "lfx-pilot")
    # Override the metadata Name to test the canonicalize path.
    dist._name = "LFX_Pilot"
    roots = installed_extension_roots(distributions=[dist])
    assert list(roots) == ["lfx-pilot"]


def test_installed_extension_roots_ignores_distributions_without_manifest(tmp_path: Path) -> None:
    plain_dist = _FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    roots = installed_extension_roots(distributions=[plain_dist])
    assert roots == {}


def test_installed_extension_roots_handles_files_none(tmp_path: Path) -> None:
    dist = _FakeDist("orphan", tmp_path, files=None)
    roots = installed_extension_roots(distributions=[dist])
    assert roots == {}


def test_manifest_owning_distributions_is_set_of_canonical_names(tmp_path: Path) -> None:
    dist = _make_installed_extension(tmp_path, "lfx-pilot")
    other = _FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    owners = manifest_owning_distributions(distributions=[dist, other])
    assert owners == frozenset({"lfx-pilot"})


def test_filter_plugin_entry_points_skips_manifest_shipping_distribution(tmp_path: Path) -> None:
    """Manifest-first precedence: AC test for "loaded once via manifest".

    Package with manifest + legacy component entry-point loads its
    components ONCE via the manifest, not twice.  We model "loaded once"
    by partitioning the entry points: the manifest's distribution lands in
    ``skipped`` (the loader's manifest path will register them), while
    non-component entry-points on a distribution that does NOT ship a
    manifest are kept (the legacy path still runs for those).
    """
    manifest_dist = _make_installed_extension(tmp_path, "lfx-pilot")
    other_dist = _FakeDist("legacy-pkg", tmp_path, files=[Path("legacy_pkg/__init__.py")])

    eps = [
        _FakeEntryPoint("PilotComponent", manifest_dist),  # should be skipped
        _FakeEntryPoint("LegacyComponent", other_dist),  # should be kept
    ]
    kept, skipped = filter_plugin_entry_points(
        eps,
        skip=manifest_owning_distributions(distributions=[manifest_dist, other_dist]),
    )
    assert [ep.name for ep in kept] == ["LegacyComponent"]
    assert [ep.name for ep in skipped] == ["PilotComponent"]


def test_filter_plugin_entry_points_keeps_entry_points_without_distribution() -> None:
    """Defensive: dist=None on an EntryPoint shouldn't drop it.

    Some Python packagers expose entry points without a back-reference to
    the owning distribution (e.g. older wheel formats).  We err on the side
    of compatibility and keep those entry points.
    """
    ep = _FakeEntryPoint("Orphan", None)
    kept, skipped = filter_plugin_entry_points([ep], skip=frozenset({"lfx-pilot"}))
    assert kept == [ep]
    assert skipped == []


def test_filter_plugin_entry_points_uses_real_distributions_by_default(tmp_path: Path) -> None:
    """When ``skip`` is omitted, the filter consults the real environment.

    The default value calls into ``importlib.metadata.distributions``; we
    don't expect any test-runtime distribution to ship an extension
    manifest, so the result is a no-op partition (everything kept).  This
    exercises the default-path code without coupling the test to the host
    environment's installed packages.
    """
    plain = _FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    ep = _FakeEntryPoint("PlainComponent", plain)
    kept, skipped = filter_plugin_entry_points([ep])
    assert kept == [ep]
    assert skipped == []


def test_canonicalize_distribution_matches_pep503() -> None:
    assert _canonicalize_distribution("Lfx-Pilot") == "lfx-pilot"
    assert _canonicalize_distribution("lfx_pilot") == "lfx-pilot"
    assert _canonicalize_distribution("LFX...PILOT") == "lfx-pilot"


# ---------------------------------------------------------------------------
# Path-safety: symlink-escape after validate
# ---------------------------------------------------------------------------


def test_load_extension_rejects_symlink_escape(tmp_path: Path) -> None:
    """A symlink under the bundle that points outside is silently skipped.

    The path-safety check in ``_iter_bundle_python_files`` quietly ignores
    escaping symlinks rather than aborting the load: we want ``ok=True`` if
    the in-tree files are fine, with the offending symlink simply absent
    from the registry.  ``path-escape`` errors at the bundle-root level are
    raised by ``_resolve_bundle_path`` and exercised in test_validate.py.
    """
    files = {"thing.py": _component_source()}
    root = _make_extension(tmp_path, files=files)
    bundle_dir = root / "components"
    outside = tmp_path / "outside.py"
    outside.write_text("class Component: pass\nclass Outside(Component):\n    pass\n", encoding="utf-8")
    symlink = bundle_dir / "outside_link.py"
    try:
        symlink.symlink_to(outside)
    except OSError:
        pytest.skip("filesystem does not support symlinks")
    result = load_extension(root)
    # Only the in-tree component registers.
    assert {c.class_name for c in result.components} == {"PilotThing"}


# ---------------------------------------------------------------------------
# LoadResult / LoadedComponent shape
# ---------------------------------------------------------------------------


def test_load_result_default_is_ok() -> None:
    result = LoadResult()
    assert result.ok
    assert bool(result) is True
    assert result.components == []


def test_loaded_component_namespaced_id_format() -> None:
    class Dummy:
        pass

    component = LoadedComponent(
        extension_id="lfx-pilot",
        extension_version="1.2.3",
        bundle="pilot",
        class_name="PilotThing",
        slot=SLOT_OFFICIAL,
        klass=Dummy,
        module_name="_lfx_ext.official.pilot.thing",
        file_path=Path("/tmp/thing.py"),
    )
    assert component.namespaced_id == "ext:pilot:PilotThing@official"


def test_load_extension_invalid_slot_raises() -> None:
    with pytest.raises(ValueError, match="slot must be one of"):
        load_extension("/tmp", slot="bogus")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Error code reachability: every loader-specific code is producible.
# ---------------------------------------------------------------------------


_LOADER_CODES = {
    "module-import-failed",
    "duplicate-component-name",
    "duplicate-inline-bundle",
    "inline-bundle-name-invalid",
}


def test_all_loader_error_codes_are_in_registry() -> None:
    from lfx.extension.errors import ERROR_CODES

    for code in _LOADER_CODES:
        assert code in ERROR_CODES, f"Loader code {code!r} missing from ERROR_CODES"


# Module-level smoke: importlib.metadata typing.
def test_importlib_metadata_distribution_is_available() -> None:
    assert hasattr(importlib_metadata, "distributions")
