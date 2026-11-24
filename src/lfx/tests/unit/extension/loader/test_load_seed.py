"""Tests for ``load_seed_extensions`` -- the filesystem-resident @official source.

Covers the deployment-doc contract: an immediate subdirectory of
``$LANGFLOW_SEED_DIR`` (or the default ``/opt/langflow/bundles/``) that
ships a v0 manifest is loaded at the @official slot, identical in shape to
a pip-installed distribution. Configured-but-missing roots emit a typed
``seed-directory-not-found`` error; the default-and-absent case is a silent
no-op so Mode A laptops do not pay for a missing ``/opt`` path.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from lfx.extension import (
    SLOT_OFFICIAL,
    load_seed_extensions,
)

from .conftest import make_extension

if TYPE_CHECKING:
    from pathlib import Path


def _seed_subdir(seed_root: Path, extension_id: str, *, bundle_name: str = "pilot") -> Path:
    """Lay out a synthetic seed-directory subdirectory."""
    sub = seed_root / extension_id
    sub.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": extension_id,
        "version": "0.1.0",
        "name": extension_id,
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": bundle_name, "path": "components"}],
    }
    return make_extension(sub, manifest=manifest)


def test_seed_default_absent_is_silent_no_op(tmp_path: Path) -> None:
    """Mode A: $LANGFLOW_SEED_DIR unset and the default doesn't exist -> []."""
    results = load_seed_extensions(seed_dir_env="", default_seed_dir=tmp_path / "does-not-exist")
    assert results == []


def test_seed_directory_loads_each_subdirectory(tmp_path: Path) -> None:
    """Two subdirectories under the seed root each load at @official."""
    seed_root = tmp_path / "bundles"
    seed_root.mkdir()
    _seed_subdir(seed_root, "lfx-alpha", bundle_name="alpha")
    _seed_subdir(seed_root, "lfx-bravo", bundle_name="bravo")

    results = load_seed_extensions(seed_dir_env=str(seed_root), default_seed_dir=None)
    by_bundle = {r.bundle: r for r in results if r.bundle}
    assert set(by_bundle) == {"alpha", "bravo"}
    for bundle, result in by_bundle.items():
        assert result.ok, [e.code for e in result.errors]
        assert result.slot == SLOT_OFFICIAL
        # Seed records carry no distribution -- they are filesystem-resident.
        assert result.distribution is None
        # Components inherit the slot/bundle.
        for comp in result.components:
            assert comp.slot == SLOT_OFFICIAL
            assert comp.bundle == bundle
            assert comp.distribution is None


def test_seed_skips_subdirectories_without_a_manifest(tmp_path: Path) -> None:
    """Operators stage non-extension content alongside bundles -> silent skip."""
    seed_root = tmp_path / "bundles"
    seed_root.mkdir()
    _seed_subdir(seed_root, "lfx-alpha")
    # README, scripts, etc.
    (seed_root / "README.md").write_text("not an extension")
    notes = seed_root / "operator-notes"
    notes.mkdir()
    (notes / "todo.txt").write_text("ignore me")

    results = load_seed_extensions(seed_dir_env=str(seed_root), default_seed_dir=None)
    bundles = [r.bundle for r in results if r.bundle]
    assert bundles == ["pilot"]


def test_seed_directory_missing_emits_typed_error(tmp_path: Path) -> None:
    """An explicitly configured seed root that is absent surfaces an error."""
    missing = tmp_path / "no-such-dir"
    results = load_seed_extensions(seed_dir_env=str(missing), default_seed_dir=None)

    sentinel_errors = [err for r in results for err in r.errors]
    codes = {err.code for err in sentinel_errors}
    assert "seed-directory-not-found" in codes
    # No component records came back: the directory was empty.
    assert all(not r.components for r in results)


def test_seed_invalid_manifest_emits_typed_error(tmp_path: Path) -> None:
    """A subdirectory with a malformed manifest surfaces a typed load error."""
    seed_root = tmp_path / "bundles"
    seed_root.mkdir()
    bad = seed_root / "lfx-broken"
    bad.mkdir()
    (bad / "extension.json").write_text("{not-valid-json")

    results = load_seed_extensions(seed_dir_env=str(seed_root), default_seed_dir=None)
    codes = {err.code for r in results for err in r.errors}
    # Either the discovery layer reports manifest-invalid, or load_extension
    # does -- both are acceptable; we just want it surfaced as a typed error.
    assert codes & {"manifest-invalid", "manifest-not-found"}


def test_seed_results_are_deterministic(tmp_path: Path) -> None:
    """Order is sorted by subdirectory path so events emit deterministically."""
    seed_root = tmp_path / "bundles"
    seed_root.mkdir()
    _seed_subdir(seed_root, "lfx-charlie", bundle_name="charlie")
    _seed_subdir(seed_root, "lfx-alpha", bundle_name="alpha")
    _seed_subdir(seed_root, "lfx-bravo", bundle_name="bravo")

    results = load_seed_extensions(seed_dir_env=str(seed_root), default_seed_dir=None)
    bundles = [r.bundle for r in results if r.bundle]
    assert bundles == ["alpha", "bravo", "charlie"]


def test_pathsep_split_loads_multiple_seed_roots(tmp_path: Path) -> None:
    """``$LANGFLOW_SEED_DIR`` is pathsep-separated for multiple roots."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _seed_subdir(root_a, "lfx-a", bundle_name="aa")
    _seed_subdir(root_b, "lfx-b", bundle_name="bb")

    env = os.pathsep.join([str(root_a), str(root_b)])
    results = load_seed_extensions(seed_dir_env=env, default_seed_dir=None)
    bundles = sorted(r.bundle for r in results if r.bundle)
    assert bundles == ["aa", "bb"]


def test_default_seed_dir_used_when_env_unset(tmp_path: Path) -> None:
    """An unset env var falls back to ``default_seed_dir``."""
    seed_root = tmp_path / "default-bundles"
    seed_root.mkdir()
    _seed_subdir(seed_root, "lfx-default", bundle_name="defaultbundle")

    results = load_seed_extensions(seed_dir_env="", default_seed_dir=seed_root)
    bundles = [r.bundle for r in results if r.bundle]
    assert bundles == ["defaultbundle"]
