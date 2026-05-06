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


def test_handles_none_paths() -> None:
    assert discover_inline_bundles(None) == []


def test_skips_non_existent_path(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    results = discover_inline_bundles([bogus])
    assert results == []
