"""Unit tests for component index hash history functionality."""

import sys
from pathlib import Path

# Add scripts directory to path so we can import the build script
scripts_dir = Path(__file__).parent.parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from build_component_index import (
    _compare_versions,
    _create_history_entry,
    _find_component_in_index,
    _load_index_from_file,
    _merge_hash_history,
    _normalize_for_determinism,
    _strip_dynamic_fields,
)

# Tests for _merge_hash_history (simplified - no previous hash history yet)


def test_merge_hash_history_new_component():
    """Test creating hash history for a new component."""
    current_component = {"metadata": {"code_hash": "abc123def456"}}
    previous_component = None
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "abc123def456"
    assert history[0]["version_first"] == "1.7.1"
    assert history[0]["version_last"] == "1.7.1"


def test_merge_hash_history_unchanged_hash():
    """Test that unchanged hash creates a single entry (no history in previous index yet)."""
    current_component = {"metadata": {"code_hash": "abc123def456"}}
    previous_component = {
        "metadata": {
            "code_hash": "abc123def456",  # Same hash, but no hash_history field
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "abc123def456"
    assert history[0]["version_first"] == "1.7.1"
    assert history[0]["version_last"] == "1.7.1"


def test_merge_hash_history_changed_hash():
    """Test that changed hash creates a single entry for the new hash."""
    current_component = {"metadata": {"code_hash": "new_hash_xyz"}}
    previous_component = {
        "metadata": {
            "code_hash": "old_hash_abc",  # Different hash, but no hash_history field
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "new_hash_xyz"
    assert history[0]["version_first"] == "1.7.1"
    assert history[0]["version_last"] == "1.7.1"


def test_merge_hash_history_no_previous_hash():
    """Test handling when previous component has no hash."""
    current_component = {"metadata": {"code_hash": "abc123"}}
    previous_component = {
        "metadata": {}  # No code_hash
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "abc123"
    assert history[0]["version_first"] == "1.7.1"
    assert history[0]["version_last"] == "1.7.1"


def test_merge_hash_history_empty_hash():
    """Test that empty hash returns empty history."""
    current_component = {"metadata": {"code_hash": ""}}
    previous_component = None
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert history == []


def test_merge_hash_history_missing_hash():
    """Test that missing hash returns empty history."""
    current_component = {"metadata": {}}
    previous_component = None
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert history == []


# Tests for helper functions


def test_load_index_from_file_nonexistent():
    """Test loading a non-existent index returns None."""
    from pathlib import Path

    result = _load_index_from_file(Path("/nonexistent/path/index.json"))

    assert result is None


def test_find_component_in_index():
    """Test finding a component in the index."""
    index = {
        "entries": [
            ["agents", {"MyAgent": {"metadata": {"code_hash": "abc123"}}}],
            ["data", {"FileLoader": {"metadata": {"code_hash": "def456"}}}],
        ]
    }

    # Found
    result = _find_component_in_index(index, "agents", "MyAgent")
    assert result is not None
    assert result["metadata"]["code_hash"] == "abc123"

    # Not found - wrong category
    result = _find_component_in_index(index, "wrong_category", "MyAgent")
    assert result is None

    # Not found - wrong component name
    result = _find_component_in_index(index, "agents", "WrongName")
    assert result is None


def test_find_component_in_index_malformed():
    """Test that malformed index entries are handled gracefully."""
    # Malformed entries should be skipped
    index = {
        "entries": [
            "not_a_tuple",  # Invalid: not a tuple/list
            ["only_one_element"],  # Invalid: wrong length
            ["category", "not_a_dict"],  # Invalid: second element not a dict
            ["agents", {"MyAgent": {"metadata": {"code_hash": "abc123"}}}],  # Valid
        ]
    }

    # Should still find the valid entry
    result = _find_component_in_index(index, "agents", "MyAgent")
    assert result is not None
    assert result["metadata"]["code_hash"] == "abc123"


def test_create_history_entry():
    """Test creating a hash history entry."""
    entry = _create_history_entry("abc123", "1.7.1")

    assert entry["hash"] == "abc123"
    assert entry["version_first"] == "1.7.1"
    assert entry["version_last"] == "1.7.1"


# Tests for version comparison


def test_compare_versions_basic():
    """Test basic version comparison."""
    assert _compare_versions("1.7.0", "1.7.1") == -1
    assert _compare_versions("1.7.1", "1.7.0") == 1
    assert _compare_versions("1.7.1", "1.7.1") == 0


def test_compare_versions_nightly_numeric():
    """Test nightly version comparison with numeric suffixes."""
    assert _compare_versions("1.7.1.dev1", "1.7.1.dev2") == -1
    assert _compare_versions("1.7.1.dev9", "1.7.1.dev10") == -1  # Numeric, not lexical
    assert _compare_versions("1.7.1.dev10", "1.7.1.dev11") == -1
    assert _compare_versions("1.7.1.dev99", "1.7.1.dev100") == -1


def test_compare_versions_nightly_date():
    """Test nightly version comparison with date-based suffixes."""
    assert _compare_versions("1.7.1.dev20260107", "1.7.1.dev20260108") == -1
    assert _compare_versions("1.7.1.dev20260108", "1.7.1.dev20260107") == 1
    assert _compare_versions("1.7.1.dev20260107", "1.7.1.dev20260107") == 0


def test_compare_versions_dev_vs_release():
    """Test that dev versions come before release versions."""
    assert _compare_versions("1.7.1.dev10", "1.7.1") == -1  # Dev < release
    assert _compare_versions("1.7.1", "1.7.1.dev10") == 1  # Release > dev
    assert _compare_versions("1.7.0", "1.7.1.dev1") == -1  # Previous release < next dev


def test_compare_versions_mixed_formats():
    """Test comparison of mixed nightly formats."""
    assert _compare_versions("1.7.1.dev10", "1.7.1.dev20260107") == -1
    assert _compare_versions("1.7.1.dev20260107", "1.7.1.dev10") == 1


# Tests for deterministic serialization


def test_normalize_for_determinism_dict():
    """Test that dicts are sorted by key."""
    obj = {"z": 1, "a": 2, "m": 3}
    result = _normalize_for_determinism(obj)

    # Keys should be in sorted order
    assert list(result.keys()) == ["a", "m", "z"]


def test_normalize_for_determinism_nested():
    """Test that nested structures are normalized."""
    obj = {"z": {"nested_z": 1, "nested_a": 2}, "a": [{"list_z": 1, "list_a": 2}]}
    result = _normalize_for_determinism(obj)

    # Top level sorted
    assert list(result.keys()) == ["a", "z"]
    # Nested dict sorted
    assert list(result["z"].keys()) == ["nested_a", "nested_z"]
    # Dict in list sorted
    assert list(result["a"][0].keys()) == ["list_a", "list_z"]


def test_normalize_for_determinism_preserves_list_order():
    """Test that list order is preserved (semantically ordered)."""
    obj = {"items": [3, 1, 2]}
    result = _normalize_for_determinism(obj)

    # List order should be preserved
    assert result["items"] == [3, 1, 2]


def test_strip_dynamic_fields():
    """Test that dynamic fields are removed."""
    obj = {
        "hash": "abc123",
        "version": "1.7.1",
        "timestamp": "2024-01-01T00:00:00Z",  # Should be removed
        "deprecated_at": "2024-06-01",  # Should be removed
        "nested": {
            "data": "keep",
            "timestamp": "remove",  # Should be removed
        },
    }

    result = _strip_dynamic_fields(obj)

    assert "hash" in result
    assert "version" in result
    assert "timestamp" not in result
    assert "deprecated_at" not in result
    assert "data" in result["nested"]
    assert "timestamp" not in result["nested"]


# Made with Bob
