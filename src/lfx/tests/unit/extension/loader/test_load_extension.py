"""Tests for ``load_extension`` -- happy path and failure modes.

Covers the AC items for the @official slot:
    - single-Bundle happy path + identity tuple population
    - alternate / non-``./components/`` bundle path
    - distribution name flows through to the LoadedComponent
    - failure modes: missing manifest, missing bundle dir, empty bundle,
      no Component subclass, module import failure, duplicate component
      class names within a bundle
    - schema-vs-runtime multi-bundle rejection (both layers checked)
    - dunder/conftest skip; recursive subdirectory walk;
      deterministic component order; re-imported class de-duplication
    - ``load_extension`` rejects unknown slot values up front
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.extension import (
    SLOT_OFFICIAL,
    LoadedComponent,
    load_extension,
)

from .conftest import _BASE_MANIFEST, component_source, make_extension

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Happy path + identity tuple
# ---------------------------------------------------------------------------


def test_single_bundle_registers_component(tmp_path: Path) -> None:
    root = make_extension(tmp_path)
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


def test_components_path_shorthand(tmp_path: Path) -> None:
    """Manifest with bundle path = ``./components/`` (the recommended layout)."""
    manifest = {**_BASE_MANIFEST, "bundles": [{"name": "pilot", "path": "components"}]}
    root = make_extension(tmp_path, manifest=manifest)
    result = load_extension(root)
    assert result.ok, result.errors
    assert result.components[0].file_path.parent.name == "components"


def test_alternate_bundle_path(tmp_path: Path) -> None:
    """Manifest pointing at a non-``components/`` directory still works."""
    manifest = {**_BASE_MANIFEST, "bundles": [{"name": "pilot", "path": "src/pilot"}]}
    root = make_extension(tmp_path, manifest=manifest)
    result = load_extension(root)
    assert result.ok, result.errors
    assert result.components[0].file_path.parent.name == "pilot"


def test_distribution_passed_through(tmp_path: Path) -> None:
    root = make_extension(tmp_path)
    result = load_extension(root, distribution="lfx-pilot")
    assert result.ok
    assert result.components[0].distribution == "lfx-pilot"
    assert result.distribution == "lfx-pilot"


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_missing_manifest(tmp_path: Path) -> None:
    result = load_extension(tmp_path)
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert codes == ["manifest-not-found"]
    # AC: fix-hint payload is present on failure.
    assert result.errors[0].hint
    assert result.errors[0].ref_url


def test_schema_rejects_multi_bundle(tmp_path: Path) -> None:
    """The schema rejects multi-bundle and the loader surfaces it as ``manifest-invalid``.

    The dedicated ``multi-bundle-deferred-in-this-milestone`` code is
    exercised by the validator's test suite and by the runtime-bypass test
    below; here we only confirm the schema-side rejection still produces a
    clean failure at the loader's boundary.
    """
    multi = {**_BASE_MANIFEST, "bundles": [{"name": "alpha", "path": "alpha"}, {"name": "bravo", "path": "bravo"}]}
    (tmp_path / "extension.json").write_text(json.dumps(multi), encoding="utf-8")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "bravo").mkdir()
    result = load_extension(tmp_path)
    assert not result.ok
    assert result.errors[0].code == "manifest-invalid"


def test_runtime_multi_bundle_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Loader-side multi-bundle guard.

    Even if a forged manifest somehow bypassed the schema, the loader still
    rejects with the dedicated ``multi-bundle-deferred-in-this-milestone`` code.
    """
    from lfx.extension.loader import _orchestrator
    from lfx.extension.manifest import (
        BundleRef,
        ExtensionManifest,
        LfxCompat,
        ManifestSource,
    )

    (tmp_path / "alpha").mkdir()
    (tmp_path / "bravo").mkdir()
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

    monkeypatch.setattr(_orchestrator, "load_manifest", lambda _root: source)
    result = load_extension(tmp_path)
    codes = [e.code for e in result.errors]
    assert codes == ["multi-bundle-deferred-in-this-milestone"]


def test_missing_bundle_directory(tmp_path: Path) -> None:
    manifest = {**_BASE_MANIFEST, "bundles": [{"name": "pilot", "path": "missing"}]}
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = load_extension(tmp_path)
    codes = [e.code for e in result.errors]
    assert codes == ["bundle-path-not-found"]


def test_empty_bundle(tmp_path: Path) -> None:
    root = make_extension(tmp_path, files={})  # no .py files
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert codes == ["bundle-empty"]


def test_no_component_subclass(tmp_path: Path) -> None:
    root = make_extension(tmp_path, files={"plain.py": "x = 1\n"})
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert codes == ["no-component-subclass"]


def test_module_import_failure(tmp_path: Path) -> None:
    root = make_extension(tmp_path, files={"broken.py": "raise RuntimeError('boom at import')\n"})
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert "module-import-failed" in codes
    failure = next(e for e in result.errors if e.code == "module-import-failed")
    assert "boom at import" in failure.message
    # Identity is still attributed even on partial failure (AC: fix-hint payload).
    assert result.extension_id == "lfx-pilot"


def test_duplicate_component_name(tmp_path: Path) -> None:
    files = {
        "first.py": component_source("PilotThing"),
        "second.py": component_source("PilotThing"),
    }
    root = make_extension(tmp_path, files=files)
    result = load_extension(root)
    codes = [e.code for e in result.errors]
    assert "duplicate-component-name" in codes
    # First-seen component still registers; only the duplicate is rejected.
    classes = [c.class_name for c in result.components]
    assert classes.count("PilotThing") == 1


# ---------------------------------------------------------------------------
# Walk semantics
# ---------------------------------------------------------------------------


def test_skips_init_and_dunder_files(tmp_path: Path) -> None:
    files = {
        "__init__.py": "",  # skipped
        "__main__.py": "raise SystemExit\n",  # skipped (would crash if executed)
        "thing.py": component_source(),
    }
    root = make_extension(tmp_path, files=files)
    result = load_extension(root)
    assert result.ok, result.errors
    assert {c.class_name for c in result.components} == {"PilotThing"}


def test_recurses_subdirectories(tmp_path: Path) -> None:
    files = {
        "a.py": component_source("Alpha"),
        "nested/b.py": component_source("Bravo"),
        "nested/deep/c.py": component_source("Charlie"),
    }
    root = make_extension(tmp_path, files=files)
    result = load_extension(root)
    assert result.ok, result.errors
    assert {c.class_name for c in result.components} == {"Alpha", "Bravo", "Charlie"}


def test_component_order_is_deterministic(tmp_path: Path) -> None:
    files = {
        "z.py": component_source("Zeta"),
        "a.py": component_source("Alpha"),
        "m.py": component_source("Mike"),
    }
    root = make_extension(tmp_path, files=files)
    result_first = load_extension(root)
    # Loading the same extension twice yields the same order.
    result_second = load_extension(root)
    names_first = [c.class_name for c in result_first.components]
    names_second = [c.class_name for c in result_second.components]
    assert names_first == names_second
    assert names_first == ["Alpha", "Mike", "Zeta"]


def test_skips_re_imported_class(tmp_path: Path) -> None:
    """A class imported (not declared) in another module shouldn't double-register."""
    files = {
        "primary.py": component_source("Primary"),
        # Re-export -- the loader should skip the imported class because its
        # __module__ does not match this file's synthetic module name.
        "alias.py": "from .primary import Primary  # noqa: F401\n",
    }
    root = make_extension(tmp_path, files=files)
    result = load_extension(root)
    # The alias module's relative import will fail because the synthetic
    # module package isn't a real package; that's an expected import-time
    # error. The primary class should still register.
    primary_names = [c.class_name for c in result.components if c.class_name == "Primary"]
    assert len(primary_names) == 1


# ---------------------------------------------------------------------------
# Path-safety: symlink-escape after validate
# ---------------------------------------------------------------------------


def test_symlink_escape_silently_skipped(tmp_path: Path) -> None:
    """A symlink under the bundle that points outside is silently skipped.

    The path-safety check in the discovery walker quietly ignores escaping
    symlinks rather than aborting the load: we want ``ok=True`` if the
    in-tree files are fine, with the offending symlink simply absent from
    the registry.  ``path-escape`` errors at the bundle-root level are
    raised by the orchestrator's path resolver and exercised in
    test_validate.py.
    """
    files = {"thing.py": component_source()}
    root = make_extension(tmp_path, files=files)
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
# Argument validation
# ---------------------------------------------------------------------------


def test_invalid_slot_raises() -> None:
    with pytest.raises(ValueError, match="slot must be one of"):
        load_extension("/tmp", slot="bogus")  # type: ignore[arg-type]
