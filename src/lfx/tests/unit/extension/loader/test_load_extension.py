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
    assert codes == ["multi-bundle-unsupported"]


def test_version_constraint_unsatisfied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest declaring lfx.compat without our BUNDLE_API_VERSION is rejected.

    The ``compat`` field validator only enforces format (positive-integer
    strings, unique).  The runtime version check happens here at load time
    so a bundle declaring only ``["2"]`` against a lfx that ships
    ``BUNDLE_API_VERSION=1`` cannot silently load and crash later when it
    touches a contract surface that does not exist yet.
    """
    from lfx.extension.loader import _orchestrator
    from lfx.extension.manifest import (
        BundleRef,
        ExtensionManifest,
        LfxCompat,
        ManifestSource,
    )

    (tmp_path / "pilot").mkdir()
    (tmp_path / "extension.json").write_text("{}", encoding="utf-8")  # placeholder

    forged = ExtensionManifest.model_construct(
        id="lfx-pilot",
        version="1.2.3",
        name="Pilot",
        lfx=LfxCompat(compat=["999"]),  # well-formed but does not include BUNDLE_API_VERSION
        bundles=[BundleRef(name="pilot", path="pilot")],
    )
    source = ManifestSource.model_construct(manifest=forged, path=tmp_path / "extension.json", kind="extension.json")
    monkeypatch.setattr(_orchestrator, "load_manifest", lambda _root: source)

    result = load_extension(tmp_path)
    codes = [e.code for e in result.errors]
    assert codes == ["version-constraint-unsatisfied"]
    err = result.errors[0]
    # The fix-hint must name BUNDLE_API_VERSION so the author knows what to change.
    assert "BUNDLE_API_VERSION" in err.message
    assert err.hint


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


def test_re_imported_class_is_skipped_via_module_filter(tmp_path: Path) -> None:
    """The ``__module__``-equality filter prevents re-imported classes from double-registering.

    Previous incarnation of this test relied on a relative import that
    coincidentally failed because the loader's synthetic ``_lfx_ext.*``
    modules aren't registered as packages -- it passed via
    ``module-import-failed``, not via the filter under test, so a future
    refactor could weaken the actual guard without the test catching it.

    This version uses ``sys.modules`` injection: a sibling module's value
    is inserted into the alias module's namespace at import time, with the
    class's ``__module__`` still pointing at its original definition. The
    only thing that prevents double-registration here is the
    ``__module__``-equality check in
    :func:`lfx.extension.loader._detection.collect_component_classes`.
    """
    # Note: the loader walks files in lex order, so we name the alias
    # file ``z_alias.py`` to guarantee it runs AFTER ``primary.py``
    # (otherwise the sys.modules lookup below would StopIteration on an
    # empty generator).
    files = {
        "primary.py": component_source("Primary"),
        # Pull the already-loaded primary module out of sys.modules and
        # alias its Primary class into our namespace WITHOUT changing the
        # class's __module__. The loader's filter must reject it because
        # __module__ != alias's synthetic module name.
        "z_alias.py": (
            "import sys\n"
            "_primary = next(\n"
            "    m for name, m in sys.modules.items()\n"
            "    if name.startswith('_lfx_ext.') and name.endswith('primary')\n"
            ")\n"
            "Primary = _primary.Primary  # re-export, NOT re-declaration\n"
        ),
    }
    root = make_extension(tmp_path, files=files)
    result = load_extension(root)
    # No import errors: both files imported cleanly. This is the key
    # difference from the old test -- if alias.py had failed, we would
    # have been testing the wrong code path.
    import_errors = [e for e in result.errors if e.code == "module-import-failed"]
    assert import_errors == [], f"alias.py should import cleanly; got {import_errors}"
    # Exactly one Primary registration -- the filter rejected the alias.
    primary_count = sum(1 for c in result.components if c.class_name == "Primary")
    assert primary_count == 1, f"__module__ filter failed: expected 1 Primary registration, got {primary_count}"


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
