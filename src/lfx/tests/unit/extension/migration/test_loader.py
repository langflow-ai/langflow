"""Tests for the migration table loader."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from lfx.extension.migration import loader as loader_mod
from lfx.extension.migration.loader import (
    MIGRATION_TABLE_PATH,
    invalidate_cache,
    load_migration_table,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    invalidate_cache()


@pytest.mark.unit
def test_canonical_table_loads() -> None:
    """The shipped migration_table.json must always parse cleanly."""
    table, error = load_migration_table()
    assert error is None
    assert table is not None
    assert table.schema_version == 1


@pytest.mark.unit
def test_canonical_path_lives_in_lfx_package() -> None:
    """Sanity: the canonical path is inside the lfx wheel layout."""
    assert MIGRATION_TABLE_PATH.name == "migration_table.json"
    assert "extension" in MIGRATION_TABLE_PATH.parts


@pytest.mark.unit
def test_missing_file_returns_typed_error(tmp_path: Path) -> None:
    nope = tmp_path / "missing.json"
    table, error = load_migration_table(nope, use_cache=False)
    assert table is None
    assert error is not None
    assert error.code == "migration-table-missing"


@pytest.mark.unit
def test_invalid_json_returns_typed_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    table, error = load_migration_table(bad, use_cache=False)
    assert table is None
    assert error is not None
    assert error.code == "migration-table-invalid"


@pytest.mark.unit
def test_non_object_top_level_returns_typed_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    table, error = load_migration_table(bad, use_cache=False)
    assert table is None
    assert error is not None
    assert error.code == "migration-table-invalid"


@pytest.mark.unit
def test_pydantic_validation_failure_returns_typed_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        # Missing all three legacy_* fields -> validator rejects.
                        "target": "ext:openai:Foo@official",
                        "added_in": "1.10.0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    table, error = load_migration_table(bad, use_cache=False)
    assert table is None
    assert error is not None
    assert error.code == "migration-table-invalid"


@pytest.mark.unit
def test_cache_returns_same_instance() -> None:
    first, _ = load_migration_table()
    second, _ = load_migration_table()
    assert first is second
    invalidate_cache()
    third, _ = load_migration_table()
    # After invalidate_cache the parser runs again; identity will differ.
    assert third is not first
    assert third == first


@pytest.mark.unit
def test_path_override_bypasses_cache(tmp_path: Path) -> None:
    """Explicit ``path`` argument must read from disk, not the process cache.

    Mirrors the cached canonical table into a temp file so we can assert
    value-equality while still distinguishing object identity, regardless of
    what the canonical migration_table.json currently contains.  Drift in
    the canonical table no longer breaks this test.
    """
    cached, _ = load_migration_table()
    custom = tmp_path / "custom.json"
    custom.write_text(
        json.dumps(
            {
                "schema_version": cached.schema_version,
                "entries": [e.model_dump(exclude_none=True) for e in cached.entries],
                "ambiguous_bare_names": [a.model_dump(exclude_none=True) for a in cached.ambiguous_bare_names],
            }
        ),
        encoding="utf-8",
    )
    direct, _ = load_migration_table(custom)
    # Explicit path bypasses cache entirely; direct must be a fresh instance,
    # not the cached one, but should compare value-equal when content matches.
    assert direct is not cached
    assert direct == cached


@pytest.mark.unit
def test_empty_table_helper() -> None:
    table = loader_mod.empty_table()
    assert table.schema_version == 1
    assert table.entries == []
