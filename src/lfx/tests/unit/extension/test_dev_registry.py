"""Tests for ``lfx.extension.dev_registry``.

Coverage:
    - register / list / unregister round-trip
    - re-register refreshes timestamp without duplicating
    - registering a non-directory raises FileNotFoundError up front
    - state file format is schema-versioned and human-readable
    - load_dev_extensions surfaces local-extension-missing for vanished paths
    - dev_extension_component_paths returns bundle dirs callable feeds to
      ``components_path`` discovery
    - state_dir override env var is respected (test seam)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.extension import (
    BASIC_TEMPLATE,
    InitOptions,
    dev_extension_component_paths,
    init_extension,
    list_dev_extensions,
    load_dev_extensions,
    register_dev_extension,
    state_file_path,
    unregister_dev_extension,
)
from lfx.extension.init_template import (
    derive_bundle_name,
    derive_display_name,
    derive_extension_id,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the dev registry at a per-test directory.

    The registry would otherwise persist across tests under the user
    cache dir; this fixture isolates each test by forcing
    ``LANGFLOW_DEV_EXTENSIONS_DIR`` to a tmp_path subdirectory.
    """
    state_dir = tmp_path / "_state"
    state_dir.mkdir()
    monkeypatch.setenv("LANGFLOW_DEV_EXTENSIONS_DIR", str(state_dir))
    return state_dir


def _scaffold(tmp_path: Path, name: str = "my-ext") -> Path:
    target = tmp_path / name
    eid = derive_extension_id(target.name)
    options = InitOptions(
        target=target,
        extension_id=eid,
        bundle_name=derive_bundle_name(eid),
        display_name=derive_display_name(eid),
        template=BASIC_TEMPLATE,
    )
    init_extension(options)
    return target


# ---------------------------------------------------------------------------
# state_file_path / register / list
# ---------------------------------------------------------------------------


def test_state_file_lives_under_isolated_dir(isolated_state_dir: Path) -> None:
    path = state_file_path()
    assert path == isolated_state_dir / "dev_extensions.json"


def test_register_and_list(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    entry = register_dev_extension(extension_dir)
    assert entry.path == extension_dir.resolve()
    assert entry.registered_at  # ISO-8601 string

    entries = list_dev_extensions()
    assert [e.path for e in entries] == [extension_dir.resolve()]


def test_register_is_idempotent_and_refreshes_timestamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extension_dir = _scaffold(tmp_path)
    first = register_dev_extension(extension_dir)
    # Force a different timestamp by patching the clock
    import lfx.extension.dev_registry as dr

    monkeypatch.setattr(dr, "_utcnow_iso", lambda: "2099-01-01T00:00:00Z")
    second = register_dev_extension(extension_dir)
    assert second.path == first.path
    assert second.registered_at == "2099-01-01T00:00:00Z"

    # Still exactly one entry in the registry.
    entries = list_dev_extensions()
    assert len(entries) == 1


def test_register_refuses_non_directory(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        register_dev_extension(bogus)


def test_register_resolves_relative_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extension_dir = _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    relative = extension_dir.name  # e.g. "my-ext"
    entry = register_dev_extension(relative)
    assert entry.path == extension_dir.resolve()
    assert entry.path.is_absolute()


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


def test_unregister_removes_existing_entry(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    removed = unregister_dev_extension(extension_dir)
    assert removed is True
    assert list_dev_extensions() == []


def test_unregister_returns_false_for_unknown_path(tmp_path: Path) -> None:
    bogus = tmp_path / "never-registered"
    bogus.mkdir()
    removed = unregister_dev_extension(bogus)
    assert removed is False


# ---------------------------------------------------------------------------
# State file format
# ---------------------------------------------------------------------------


def test_state_file_is_versioned_json(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    payload = json.loads(state_file_path().read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert isinstance(payload["extensions"], list)
    assert payload["extensions"][0]["path"] == str(extension_dir.resolve())


def test_malformed_state_file_treated_as_empty() -> None:
    # Pre-populate the (autouse-isolated) state dir with garbage, then read it.
    state_file_path().parent.mkdir(parents=True, exist_ok=True)
    state_file_path().write_text("not valid json", encoding="utf-8")
    assert list_dev_extensions() == []


def test_missing_state_file_yields_empty_list() -> None:
    assert list_dev_extensions() == []


# ---------------------------------------------------------------------------
# load_dev_extensions
# ---------------------------------------------------------------------------


def test_load_dev_extensions_returns_loaded_components(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    results = load_dev_extensions()
    assert len(results) == 1
    result = results[0]
    assert result.ok, result.errors
    assert result.extension_id == "my-ext"
    assert any(c.class_name == "MyExtHelloComponent" for c in result.components)


def test_load_dev_extensions_surfaces_missing_directory(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    # Move the directory out from under the registry.
    relocated = tmp_path / "moved-away"
    extension_dir.rename(relocated)

    results = load_dev_extensions()
    assert len(results) == 1
    result = results[0]
    # AC #5: typed warning, not a crash.
    codes = [w.code for w in result.warnings]
    assert codes == ["local-extension-missing"]
    assert result.components == []


def test_load_dev_extensions_after_directory_returns_recovers(tmp_path: Path) -> None:
    """If a missing path reappears, the next load picks it up cleanly."""
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    relocated = tmp_path / "moved-away"
    extension_dir.rename(relocated)
    # First load -> warning
    assert any(w.code == "local-extension-missing" for r in load_dev_extensions() for w in r.warnings)
    # Move back
    relocated.rename(extension_dir)
    # Second load -> warning gone
    results = load_dev_extensions()
    assert all(not r.warnings for r in results)
    assert results[0].ok


# ---------------------------------------------------------------------------
# dev_extension_component_paths
# ---------------------------------------------------------------------------


def test_dev_extension_component_paths_returns_bundle_dir(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    paths, errors = dev_extension_component_paths()
    assert errors == []
    assert len(paths) == 1
    # Resolved path should point inside the extension's components dir.
    assert paths[0].is_relative_to(extension_dir.resolve())


def test_dev_extension_component_paths_surfaces_missing_dir(tmp_path: Path) -> None:
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    extension_dir.rename(tmp_path / "moved")
    paths, errors = dev_extension_component_paths()
    assert paths == []
    codes = [e.code for e in errors]
    assert "local-extension-missing" in codes


def test_dev_extension_component_paths_forwards_all_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A duplicate-component-name warning must reach the caller.

    Previously the helper only forwarded ``local-extension-missing``,
    silently dropping every other warning code.  This test pins the new
    "forward everything" contract so a duplicate-component-name (or any
    future code) shows up in the lifespan hook's logs.
    """
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)

    # Stub load_dev_extensions to inject a synthetic warning of a
    # different code, simulating what a future loader pass might emit.
    from lfx.extension import dev_registry as dr
    from lfx.extension.errors import ExtensionError
    from lfx.extension.loader._types import LoadResult

    fake = LoadResult(
        slot="official",
        source_path=extension_dir,
        extension_id="my-ext",
        bundle="my_ext",
    )
    fake.warnings.append(
        ExtensionError(
            code="duplicate-component-name",
            message="synthetic",
            location="my_ext",
            content="HelloComponent",
            hint="rename",
        )
    )
    monkeypatch.setattr(dr, "load_dev_extensions", lambda *_, **__: [fake])

    _paths, errors = dev_extension_component_paths()
    codes = [e.code for e in errors]
    # The non-missing-dir warning is forwarded, not silently dropped.
    assert "duplicate-component-name" in codes


def test_dev_extension_component_paths_defends_against_missing_source_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A LoadResult with components but no source_path is a contract bug.

    The helper used to silently drop such results, hiding the problem.
    Now it surfaces a typed local-extension-missing error and skips the
    extension explicitly.
    """
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)

    from lfx.extension import dev_registry as dr
    from lfx.extension.loader._types import LoadResult

    # Build a LoadResult that's structurally invalid: components present,
    # source_path None.
    fake = LoadResult(
        slot="official",
        source_path=None,
        extension_id="my-ext",
        bundle="my_ext",
    )
    # Borrow the component the real loader produced.
    real_results = dr.load_dev_extensions()
    real_components = real_results[0].components
    fake.components.extend(real_components)
    monkeypatch.setattr(dr, "load_dev_extensions", lambda *_, **__: [fake])

    paths, errors = dev_extension_component_paths()
    assert paths == []
    codes = [e.code for e in errors]
    assert "local-extension-missing" in codes


def test_dev_extension_component_paths_uses_relative_depth_for_bundle_root(
    tmp_path: Path,
) -> None:
    """The shallowest-ancestor-under-source_root algorithm picks the right dir.

    With a bundle laid out at ``my-ext/components/my_ext/`` and a real
    component at ``my-ext/components/my_ext/hello.py``, the returned
    bundle path must be the components/my_ext directory, NOT something
    higher up (which would cause the existing palette discovery to miss
    sub-modules) and NOT the file's parent directly (it happens to be
    the same here, but the algorithm should be correct).
    """
    extension_dir = _scaffold(tmp_path)
    register_dev_extension(extension_dir)
    paths, errors = dev_extension_component_paths()
    assert errors == []
    assert len(paths) == 1
    bundle_root = paths[0]
    # Path resolves to <ext>/components/my_ext (the bundle dir).
    assert bundle_root.name == "my_ext"
    assert bundle_root.parent.name == "components"
    assert bundle_root.is_relative_to(extension_dir.resolve())


# ---------------------------------------------------------------------------
# Override env var
# ---------------------------------------------------------------------------


def test_state_dir_env_var_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "custom"
    monkeypatch.setenv("LANGFLOW_DEV_EXTENSIONS_DIR", str(override))
    assert state_file_path().parent == override
    # The override is honored even when LANGFLOW_CONFIG_DIR is also set.
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path / "ignore-me"))
    assert state_file_path().parent == override


def test_config_dir_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFLOW_DEV_EXTENSIONS_DIR", raising=False)
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(cfg))
    assert state_file_path() == cfg / "extensions" / "dev_extensions.json"
