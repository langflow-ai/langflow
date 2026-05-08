"""Tests for ``discover_inline_bundles`` (LANGFLOW_COMPONENTS_PATH).

Covers the @extra-slot AC items:
    - each immediate subfolder of every path is one Bundle
    - walk order: user-declared path order, lexicographic within each path
    - first-wins on duplicate names; the loser carries a typed
      ``duplicate-inline-bundle`` warning that names both paths
    - dot-prefixed and skip-listed dirs are silently skipped
    - invalid bundle directory names emit ``inline-bundle-name-invalid``
    - optional ``bundle.json`` provides id / version
    - None or non-existent ``paths`` yield an empty result without raising
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from lfx.extension import (
    SLOT_EXTRA,
    discover_inline_bundles,
)

from .conftest import make_inline_bundle

if TYPE_CHECKING:
    from pathlib import Path


def test_loaded_from_subdirectories(tmp_path: Path) -> None:
    parent = tmp_path / "components_path"
    parent.mkdir()
    make_inline_bundle(parent, "alpha")
    make_inline_bundle(parent, "bravo")

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


def test_walk_order_is_lexicographic(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    make_inline_bundle(parent, "zeta")
    make_inline_bundle(parent, "alpha")
    make_inline_bundle(parent, "mike")
    results = discover_inline_bundles([parent])
    names = [r.bundle for r in results]
    assert names == ["alpha", "mike", "zeta"]


def test_user_declared_path_order_is_preserved(tmp_path: Path) -> None:
    """AC #8: user-declared path list order is preserved across paths.

    Distinct bundle names in two paths -> ``[path_b, path_a]`` produces
    results in the order the user declared them, not a global lex sort.
    Catches a future refactor that accidentally sorts paths globally.
    """
    path_a = tmp_path / "first"
    path_b = tmp_path / "second"
    path_a.mkdir()
    path_b.mkdir()
    # Each path holds a uniquely-named bundle so duplicate-resolution
    # never kicks in -- the assertion is purely about path order.
    make_inline_bundle(path_a, "alpha")
    make_inline_bundle(path_b, "zeta")

    # Reverse user-declared order: path_b first, then path_a.
    results = discover_inline_bundles([path_b, path_a])
    names = [r.bundle for r in results]
    # Path order beats lex order: zeta (from path_b) appears before alpha
    # (from path_a) because the user declared path_b first.
    assert names == ["zeta", "alpha"]


def test_first_wins_emits_duplicate_warning(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    make_inline_bundle(first, "shared")
    make_inline_bundle(second, "shared")

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


def test_invalid_directory_name_emits_typed_error(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    make_inline_bundle(parent, "BadName")  # uppercase -> invalid pattern
    results = discover_inline_bundles([parent])
    assert len(results) == 1
    assert results[0].errors
    assert results[0].errors[0].code == "inline-bundle-name-invalid"


def test_skips_dot_directories(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    make_inline_bundle(parent, ".hidden")
    make_inline_bundle(parent, "real")
    results = discover_inline_bundles([parent])
    assert [r.bundle for r in results] == ["real"]


def test_respects_bundle_json(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    parent.mkdir()
    bundle_dir = make_inline_bundle(parent, "alpha")
    (bundle_dir / "bundle.json").write_text(json.dumps({"id": "lfx-alpha", "version": "9.9.9"}), encoding="utf-8")
    results = discover_inline_bundles([parent])
    assert results[0].extension_id == "lfx-alpha"
    assert results[0].extension_version == "9.9.9"


def test_inline_module_import_failure_attributes_identity(tmp_path: Path) -> None:
    """AC #10: load results carry extension_id/bundle on partial failure (@extra).

    Mirror of test_module_import_failure (which covers @official) for the
    inline-bundle path: a broken.py that raises at import time produces
    a typed ``module-import-failed`` error AND the LoadResult still
    carries the bundle identity so the events pipeline can attribute the
    failure to a specific source.
    """
    parent = tmp_path / "p"
    parent.mkdir()
    make_inline_bundle(
        parent,
        "alpha",
        files={
            # One healthy file plus one that blows up at import-time.
            "thing.py": "class Component:\n    pass\nclass Thing(Component):\n    pass\n",
            "broken.py": "raise RuntimeError('boom at import')\n",
        },
    )
    results = discover_inline_bundles([parent])
    assert len(results) == 1
    result = results[0]
    # Identity is attributed even though one file failed to import.
    assert result.bundle == "alpha"
    assert result.extension_id == "alpha"  # default-derived from dir name
    assert result.extension_version  # at least the default "0.0.0"
    # Typed error surfaced.
    codes = [e.code for e in result.errors]
    assert "module-import-failed" in codes
    failure = next(e for e in result.errors if e.code == "module-import-failed")
    assert "boom at import" in failure.message
    assert failure.hint  # AC: fix-hint payload
    # Healthy sibling still loaded.
    assert any(c.class_name == "Thing" for c in result.components)


def test_handles_none_paths() -> None:
    assert discover_inline_bundles(None) == []


def test_non_existent_path_emits_inline_path_missing(tmp_path: Path) -> None:
    """A non-existent or non-dir path produces a typed warning, not silent skip.

    A typo in LANGFLOW_COMPONENTS_PATH would otherwise yield zero
    components and zero diagnostics -- the AC item the second reviewer
    flagged as a tough debug experience.
    """
    bogus = tmp_path / "does-not-exist"
    results = discover_inline_bundles([bogus])
    assert len(results) == 1
    result = results[0]
    # Path-level diagnostic: no bundle was identified.
    assert result.bundle is None
    assert any(w.code == "inline-path-missing" for w in result.warnings)
    warning = next(w for w in result.warnings if w.code == "inline-path-missing")
    assert str(bogus) in warning.location
    assert warning.hint  # AC: fix-hint payload


def test_unreadable_path_emits_inline_path_unreadable(tmp_path: Path, monkeypatch) -> None:
    """An OSError during iterdir surfaces ``inline-path-unreadable``, not a silent skip.

    Permission-denied on a configured LANGFLOW_COMPONENTS_PATH entry is a
    real misconfiguration -- the user explicitly pointed us here. The
    OSError message must be carried through so an operator can diagnose.
    """
    from pathlib import Path as _Path  # imported here to keep TYPE_CHECKING block clean

    parent = tmp_path / "p"
    parent.mkdir()

    # Patch ``Path.iterdir`` to raise PermissionError just for this dir.
    real_iterdir = _Path.iterdir

    def _fake_iterdir(self):
        if self == parent.resolve():
            msg = "Permission denied"
            raise PermissionError(msg)
        return real_iterdir(self)

    monkeypatch.setattr(_Path, "iterdir", _fake_iterdir)

    results = discover_inline_bundles([parent])
    assert len(results) == 1
    result = results[0]
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert "inline-path-unreadable" in codes
    err = next(e for e in result.errors if e.code == "inline-path-unreadable")
    assert "Permission denied" in err.message
    assert str(parent.resolve()) in err.location
    assert err.hint  # AC: fix-hint payload
