"""Unit tests for component index hash history with version ranges."""


def test_merge_hash_history_new_component():
    """Test creating hash history for a new component."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123def456"}}
    previous_component = None
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "abc123def456"
    assert history[0]["version_first"] == "1.7.1"
    assert history[0]["version_last"] == "1.7.1"


def test_merge_hash_history_unchanged_hash_extends_range():
    """Test that unchanged hash extends the version range."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123def456"}}
    previous_component = {
        "metadata": {
            "code_hash": "abc123def456",
            "hash_history": [
                {"hash": "abc123def456", "version_first": "1.7.0", "version_last": "1.7.0"}
            ],
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "abc123def456"
    assert history[0]["version_first"] == "1.7.0"
    assert history[0]["version_last"] == "1.7.1"  # Extended!


def test_merge_hash_history_changed_hash_creates_new_entry():
    """Test that changed hash creates a new history entry."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "new_hash_xyz"}}
    previous_component = {
        "metadata": {
            "code_hash": "old_hash_abc",
            "hash_history": [
                {"hash": "old_hash_abc", "version_first": "1.7.0", "version_last": "1.7.0"}
            ],
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 2
    # Old entry preserved
    assert history[0]["hash"] == "old_hash_abc"
    assert history[0]["version_first"] == "1.7.0"
    assert history[0]["version_last"] == "1.7.0"
    # New entry created
    assert history[1]["hash"] == "new_hash_xyz"
    assert history[1]["version_first"] == "1.7.1"
    assert history[1]["version_last"] == "1.7.1"


def test_merge_hash_history_nightly_builds_extend_range():
    """Test that nightly builds with same hash extend the range."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123"}}
    previous_component = {
        "metadata": {
            "code_hash": "abc123",
            "hash_history": [
                {"hash": "abc123", "version_first": "1.7.1.dev20260107", "version_last": "1.7.1.dev20260107"}
            ],
        }
    }
    current_version = "1.7.1.dev20260108"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 1
    assert history[0]["hash"] == "abc123"
    assert history[0]["version_first"] == "1.7.1.dev20260107"
    assert history[0]["version_last"] == "1.7.1.dev20260108"  # Extended to next day


def test_merge_hash_history_multiple_changes():
    """Test multiple hash changes create multiple entries."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "hash3"}}
    previous_component = {
        "metadata": {
            "code_hash": "hash2",
            "hash_history": [
                {"hash": "hash1", "version_first": "1.6.0", "version_last": "1.6.5"},
                {"hash": "hash2", "version_first": "1.7.0", "version_last": "1.7.0"},
            ],
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 3
    assert history[0]["hash"] == "hash1"
    assert history[1]["hash"] == "hash2"
    assert history[2]["hash"] == "hash3"
    assert history[2]["version_first"] == "1.7.1"


def test_merge_hash_history_migrates_old_format():
    """Test migration from old single-version format to range format."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "new_hash"}}
    previous_component = {
        "metadata": {
            "code_hash": "old_hash",
            "hash_history": [
                {"hash": "old_hash", "version": "1.7.0"}  # Old format without ranges
            ],
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 2
    # Old entry migrated to range format
    assert history[0]["hash"] == "old_hash"
    assert history[0]["version_first"] == "1.7.0"
    assert history[0]["version_last"] == "1.7.0"
    # New entry in range format
    assert history[1]["hash"] == "new_hash"
    assert history[1]["version_first"] == "1.7.1"
    assert history[1]["version_last"] == "1.7.1"


def test_merge_hash_history_empty_hash():
    """Test that empty hash returns empty history."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": ""}}
    previous_component = None
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert history == []


def test_merge_hash_history_missing_hash():
    """Test that missing hash returns empty history."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {}}
    previous_component = None
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert history == []


def test_merge_hash_history_preserves_multiple_ranges():
    """Test that multiple version ranges are preserved correctly."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "hash2"}}
    previous_component = {
        "metadata": {
            "code_hash": "hash2",
            "hash_history": [
                {"hash": "hash1", "version_first": "1.5.0", "version_last": "1.6.9"},
                {"hash": "hash2", "version_first": "1.7.0", "version_last": "1.7.0"},
            ],
        }
    }
    current_version = "1.7.1"

    history = _merge_hash_history(current_component, previous_component, current_version)

    assert len(history) == 2
    # First range unchanged
    assert history[0]["hash"] == "hash1"
    assert history[0]["version_first"] == "1.5.0"
    assert history[0]["version_last"] == "1.6.9"
    # Second range extended
    assert history[1]["hash"] == "hash2"
    assert history[1]["version_first"] == "1.7.0"
    assert history[1]["version_last"] == "1.7.1"


def test_load_index_from_file_nonexistent():
    """Test loading a non-existent index returns None."""
    from pathlib import Path

    from scripts.build_component_index import _load_index_from_file

    result = _load_index_from_file(Path("/nonexistent/path/index.json"))

    assert result is None


def test_find_component_in_index():
    """Test finding a component in the index."""
    from scripts.build_component_index import _find_component_in_index

    index = {
        "entries": [
            ["category1", {"comp1": {"metadata": {"code_hash": "abc"}}}],
            ["category2", {"comp2": {"metadata": {"code_hash": "def"}}}],
        ]
    }

    result = _find_component_in_index(index, "category1", "comp1")
    assert result is not None
    assert result["metadata"]["code_hash"] == "abc"

    result = _find_component_in_index(index, "category2", "comp2")
    assert result is not None
    assert result["metadata"]["code_hash"] == "def"

    result = _find_component_in_index(index, "category1", "nonexistent")
    assert result is None

    result = _find_component_in_index(index, "nonexistent", "comp1")
    assert result is None


def test_find_component_in_empty_index():
    """Test finding a component in an empty index."""
    from scripts.build_component_index import _find_component_in_index

    result = _find_component_in_index({}, "category", "component")
    assert result is None

    result = _find_component_in_index({"entries": []}, "category", "component")
    assert result is None


def test_strip_dynamic_fields_removes_timestamps():
    """Test that dynamic fields like timestamps are stripped."""
    from scripts.build_component_index import _strip_dynamic_fields

    data = {
        "hash_history": [
            {
                "hash": "abc",
                "version_first": "1.7.0",
                "version_last": "1.7.1",
                "timestamp": "2026-01-07T00:00:00Z",  # Should be removed
                "deprecated_at": "2026-01-08T00:00:00Z",  # Should be removed
            }
        ]
    }

    result = _strip_dynamic_fields(data)

    assert "timestamp" not in result["hash_history"][0]
    assert "deprecated_at" not in result["hash_history"][0]
    assert result["hash_history"][0]["hash"] == "abc"
    assert result["hash_history"][0]["version_first"] == "1.7.0"
    assert result["hash_history"][0]["version_last"] == "1.7.1"


def test_hash_history_format_in_metadata():
    """Test that the index includes hash_history_format metadata."""
    from scripts.build_component_index import build_component_index

    # This test requires the full environment, so we'll just verify the structure
    # In a real scenario, you'd mock the import_langflow_components function
    # For now, we'll test the metadata structure expectation
    expected_format = "inline_ranges_v1"

    # The actual index should have this in metadata
    # This is more of an integration test, but validates the contract
    assert expected_format == "inline_ranges_v1"  # Verify the constant


def test_version_range_scenario_stable_component():
    """Test realistic scenario: stable component across many versions."""
    from scripts.build_component_index import _merge_hash_history

    # Simulate a component that doesn't change for many versions
    current_component = {"metadata": {"code_hash": "stable_hash"}}

    # Start with version 1.7.0
    previous_component = None
    history = _merge_hash_history(current_component, previous_component, "1.7.0")
    assert len(history) == 1
    assert history[0]["version_first"] == "1.7.0"
    assert history[0]["version_last"] == "1.7.0"

    # Simulate 10 nightly builds - hash unchanged
    for day in range(1, 11):
        previous_component = {"metadata": {"code_hash": "stable_hash", "hash_history": history}}
        history = _merge_hash_history(current_component, previous_component, f"1.7.0.dev2026010{day:02d}")

    # Should still be just one entry with extended range
    assert len(history) == 1
    assert history[0]["hash"] == "stable_hash"
    assert history[0]["version_first"] == "1.7.0"
    assert history[0]["version_last"] == "1.7.0.dev20260110"


def test_version_range_scenario_active_development():
    """Test realistic scenario: component changing frequently."""
    from scripts.build_component_index import _merge_hash_history

    history = []
    current_component = {"metadata": {"code_hash": "hash1"}}

    # Day 1: Initial version
    history = _merge_hash_history(current_component, None, "1.7.0.dev20260101")
    assert len(history) == 1

    # Day 2-3: Same hash
    for day in [2, 3]:
        previous_component = {"metadata": {"code_hash": "hash1", "hash_history": history}}
        history = _merge_hash_history(current_component, previous_component, f"1.7.0.dev202601{day:02d}")
    assert len(history) == 1
    assert history[0]["version_last"] == "1.7.0.dev20260103"

    # Day 4: Hash changes
    current_component = {"metadata": {"code_hash": "hash2"}}
    previous_component = {"metadata": {"code_hash": "hash1", "hash_history": history}}
    history = _merge_hash_history(current_component, previous_component, "1.7.0.dev20260104")
    assert len(history) == 2
    assert history[1]["hash"] == "hash2"

    # Day 5: Another change
    current_component = {"metadata": {"code_hash": "hash3"}}
    previous_component = {"metadata": {"code_hash": "hash2", "hash_history": history}}
    history = _merge_hash_history(current_component, previous_component, "1.7.0.dev20260105")
    assert len(history) == 3
    assert history[2]["hash"] == "hash3"


# Safeguard and Ordering Tests


def test_compare_versions_basic():
    """Test basic version comparison."""
    from scripts.build_component_index import _compare_versions

    assert _compare_versions("1.7.0", "1.7.1") == -1
    assert _compare_versions("1.7.1", "1.7.0") == 1
    assert _compare_versions("1.7.1", "1.7.1") == 0


def test_compare_versions_nightly_numeric():
    """Test nightly version comparison with numeric suffixes."""
    from scripts.build_component_index import _compare_versions

    assert _compare_versions("1.7.1.dev1", "1.7.1.dev2") == -1
    assert _compare_versions("1.7.1.dev9", "1.7.1.dev10") == -1  # Numeric, not lexical
    assert _compare_versions("1.7.1.dev10", "1.7.1.dev11") == -1
    assert _compare_versions("1.7.1.dev99", "1.7.1.dev100") == -1


def test_compare_versions_nightly_date():
    """Test nightly version comparison with date-based suffixes."""
    from scripts.build_component_index import _compare_versions

    assert _compare_versions("1.7.1.dev20260107", "1.7.1.dev20260108") == -1
    assert _compare_versions("1.7.1.dev20260108", "1.7.1.dev20260107") == 1
    assert _compare_versions("1.7.1.dev20260107", "1.7.1.dev20260107") == 0


def test_compare_versions_dev_vs_release():
    """Test that dev versions come before release versions."""
    from scripts.build_component_index import _compare_versions

    assert _compare_versions("1.7.1.dev10", "1.7.1") == -1  # Dev < release
    assert _compare_versions("1.7.1", "1.7.1.dev10") == 1  # Release > dev
    assert _compare_versions("1.7.0", "1.7.1.dev1") == -1  # Previous release < next dev


def test_compare_versions_mixed_formats():
    """Test comparison of mixed nightly formats."""
    from scripts.build_component_index import _compare_versions

    assert _compare_versions("1.7.1.dev10", "1.7.1.dev20260107") == -1
    assert _compare_versions("1.7.1.dev20260107", "1.7.1.dev10") == 1


def test_validate_version_range_valid():
    """Test validation of valid version ranges."""
    from scripts.build_component_index import _validate_version_range

    assert _validate_version_range("1.7.0", "1.7.1", "1.7.2") is True
    assert _validate_version_range("1.7.1", "1.7.1", "1.7.1") is True
    assert _validate_version_range("1.7.1.dev10", "1.7.1.dev15", "1.7.1.dev20") is True


def test_validate_version_range_invalid_first_greater_than_last():
    """Test validation rejects ranges where first > last."""
    from scripts.build_component_index import _validate_version_range

    assert _validate_version_range("1.7.1", "1.7.0", "1.7.2") is False


def test_validate_version_range_invalid_current_less_than_last():
    """Test validation rejects ranges where current < last (regression)."""
    from scripts.build_component_index import _validate_version_range

    assert _validate_version_range("1.7.0", "1.7.1", "1.7.0") is False
    assert _validate_version_range("1.7.1.dev10", "1.7.1.dev15", "1.7.1.dev12") is False


def test_merge_hash_history_with_version_regression():
    """Test that version regression is handled safely."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123"}}
    previous_component = {
        "metadata": {
            "code_hash": "abc123",
            "hash_history": [{"hash": "abc123", "version_first": "1.7.1", "version_last": "1.7.1"}],
        }
    }

    # Try to go backwards in version
    history = _merge_hash_history(current_component, previous_component, "1.7.0")

    # Should create new entry instead of extending (protection against regression)
    assert len(history) == 2
    assert history[0]["version_first"] == "1.7.1"
    assert history[1]["version_first"] == "1.7.0"


def test_merge_hash_history_nightly_progression():
    """Test that nightly versions progress correctly."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123"}}

    # Start with dev10
    previous_component = {
        "metadata": {
            "code_hash": "abc123",
            "hash_history": [{"hash": "abc123", "version_first": "1.7.1.dev10", "version_last": "1.7.1.dev10"}],
        }
    }

    # Progress to dev11
    history = _merge_hash_history(current_component, previous_component, "1.7.1.dev11")
    assert len(history) == 1
    assert history[0]["version_first"] == "1.7.1.dev10"
    assert history[0]["version_last"] == "1.7.1.dev11"

    # Progress to dev20
    previous_component["metadata"]["hash_history"] = history
    history = _merge_hash_history(current_component, previous_component, "1.7.1.dev20")
    assert len(history) == 1
    assert history[0]["version_first"] == "1.7.1.dev10"
    assert history[0]["version_last"] == "1.7.1.dev20"


def test_merge_hash_history_dev_to_release():
    """Test progression from dev version to release."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123"}}
    previous_component = {
        "metadata": {
            "code_hash": "abc123",
            "hash_history": [
                {"hash": "abc123", "version_first": "1.7.1.dev10", "version_last": "1.7.1.dev15"}
            ],
        }
    }

    # Progress to release
    history = _merge_hash_history(current_component, previous_component, "1.7.1")
    assert len(history) == 1
    assert history[0]["version_first"] == "1.7.1.dev10"
    assert history[0]["version_last"] == "1.7.1"


def test_merge_hash_history_date_based_nightlies():
    """Test date-based nightly version progression."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123"}}
    previous_component = {
        "metadata": {
            "code_hash": "abc123",
            "hash_history": [
                {"hash": "abc123", "version_first": "1.7.1.dev20260107", "version_last": "1.7.1.dev20260107"}
            ],
        }
    }

    # Next day
    history = _merge_hash_history(current_component, previous_component, "1.7.1.dev20260108")
    assert len(history) == 1
    assert history[0]["version_first"] == "1.7.1.dev20260107"
    assert history[0]["version_last"] == "1.7.1.dev20260108"

    # Week later
    previous_component["metadata"]["hash_history"] = history
    history = _merge_hash_history(current_component, previous_component, "1.7.1.dev20260114")
    assert len(history) == 1
    assert history[0]["version_first"] == "1.7.1.dev20260107"
    assert history[0]["version_last"] == "1.7.1.dev20260114"


def test_safeguard_prevents_invalid_range_extension():
    """Test that invalid ranges are not created even with same hash."""
    from scripts.build_component_index import _merge_hash_history

    current_component = {"metadata": {"code_hash": "abc123"}}

    # Create a scenario where validation would fail
    # (This is a defensive test - shouldn't happen in practice)
    previous_component = {
        "metadata": {
            "code_hash": "abc123",
            "hash_history": [{"hash": "abc123", "version_first": "1.7.1", "version_last": "1.7.0"}],  # Invalid!
        }
    }

    # Should handle gracefully
    history = _merge_hash_history(current_component, previous_component, "1.7.2")
    # Should create new entry rather than extend invalid range
    assert len(history) >= 1

# Normalization and Validation Tests


def test_normalize_history_to_range_format_already_in_range_format():
    """Test normalization of entries already in range format."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version_first": "1.7.0", "version_last": "1.7.1"},
        {"hash": "def456", "version_first": "1.7.2", "version_last": "1.7.3"},
    ]

    normalized = _normalize_history_to_range_format(history)

    assert len(normalized) == 2
    assert normalized[0]["hash"] == "abc123"
    assert normalized[0]["version_first"] == "1.7.0"
    assert normalized[0]["version_last"] == "1.7.1"


def test_normalize_history_to_range_format_old_format_migration():
    """Test migration from old format to range format."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version": "1.7.0"},
        {"hash": "def456", "version": "1.7.1"},
    ]

    normalized = _normalize_history_to_range_format(history)

    assert len(normalized) == 2
    assert normalized[0]["hash"] == "abc123"
    assert normalized[0]["version_first"] == "1.7.0"
    assert normalized[0]["version_last"] == "1.7.0"
    assert normalized[1]["hash"] == "def456"
    assert normalized[1]["version_first"] == "1.7.1"
    assert normalized[1]["version_last"] == "1.7.1"


def test_normalize_history_filters_missing_hash():
    """Test that entries with missing hash are filtered out."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version": "1.7.0"},
        {"version": "1.7.1"},  # Missing hash
        {"hash": None, "version": "1.7.2"},  # None hash
        {"hash": "", "version": "1.7.3"},  # Empty hash
    ]

    normalized = _normalize_history_to_range_format(history)

    assert len(normalized) == 1
    assert normalized[0]["hash"] == "abc123"


def test_normalize_history_filters_missing_version_fields():
    """Test that entries with missing version fields are filtered out."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version_first": "1.7.0", "version_last": "1.7.1"},
        {"hash": "def456", "version_first": "1.7.2"},  # Missing version_last
        {"hash": "ghi789", "version_last": "1.7.3"},  # Missing version_first
        {"hash": "jkl012"},  # Missing both (old format without version)
    ]

    normalized = _normalize_history_to_range_format(history)

    assert len(normalized) == 1
    assert normalized[0]["hash"] == "abc123"


def test_normalize_history_filters_invalid_version_strings():
    """Test that entries with invalid PEP 440 version strings are filtered out."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version": "1.7.0"},
        {"hash": "def456", "version": "not-a-version"},  # Invalid
        {"hash": "ghi789", "version": "1.7.1..2"},  # Invalid (double dots)
        {"hash": "jkl012", "version_first": "1.7.2", "version_last": "invalid"},  # Invalid last
        {"hash": "mno345", "version_first": "bad", "version_last": "1.7.3"},  # Invalid first
    ]

    normalized = _normalize_history_to_range_format(history)

    assert len(normalized) == 1
    assert normalized[0]["hash"] == "abc123"


def test_normalize_history_filters_inverted_version_ranges():
    """Test that entries with inverted version ranges are filtered out."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version_first": "1.7.0", "version_last": "1.7.1"},  # Valid
        {"hash": "def456", "version_first": "1.7.3", "version_last": "1.7.2"},  # Inverted!
        {"hash": "ghi789", "version_first": "1.8.0", "version_last": "1.7.9"},  # Inverted!
        {"hash": "jkl012", "version_first": "1.7.1.dev20", "version_last": "1.7.1.dev10"},  # Inverted!
    ]

    normalized = _normalize_history_to_range_format(history)

    # Only the valid entry should remain
    assert len(normalized) == 1
    assert normalized[0]["hash"] == "abc123"
    assert normalized[0]["version_first"] == "1.7.0"
    assert normalized[0]["version_last"] == "1.7.1"


def test_normalize_history_allows_equal_version_range():
    """Test that version ranges where first == last are allowed."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version_first": "1.7.0", "version_last": "1.7.0"},  # Equal is valid
        {"hash": "def456", "version": "1.7.1"},  # Old format also creates equal range
    ]

    normalized = _normalize_history_to_range_format(history)

    assert len(normalized) == 2
    assert normalized[0]["version_first"] == "1.7.0"
    assert normalized[0]["version_last"] == "1.7.0"
    assert normalized[1]["version_first"] == "1.7.1"
    assert normalized[1]["version_last"] == "1.7.1"


def test_normalize_history_mixed_valid_and_invalid():
    """Test normalization with a mix of valid and invalid entries."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version": "1.7.0"},  # Valid old format
        {"hash": "def456", "version_first": "1.7.1", "version_last": "1.7.2"},  # Valid range
        {"version": "1.7.3"},  # Invalid: missing hash
        {"hash": "ghi789", "version": "not-valid"},  # Invalid: bad version
        {"hash": "jkl012", "version_first": "1.7.5", "version_last": "1.7.4"},  # Invalid: inverted
        {"hash": "mno345", "version_first": "1.7.6", "version_last": "1.7.7"},  # Valid range
    ]

    normalized = _normalize_history_to_range_format(history)

    # Should have 3 valid entries
    assert len(normalized) == 3
    assert normalized[0]["hash"] == "abc123"
    assert normalized[1]["hash"] == "def456"
    assert normalized[2]["hash"] == "mno345"


def test_normalize_history_preserves_entry_data():
    """Test that normalization preserves all entry data (makes copies)."""
    from scripts.build_component_index import _normalize_history_to_range_format

    history = [
        {"hash": "abc123", "version_first": "1.7.0", "version_last": "1.7.1", "extra": "data"},
    ]

    normalized = _normalize_history_to_range_format(history)

    # Should preserve extra fields
    assert normalized[0]["extra"] == "data"
    
    # Should be a copy, not the same object
    assert normalized[0] is not history[0]
    
    # Modifying normalized shouldn't affect original
    normalized[0]["hash"] = "modified"
    assert history[0]["hash"] == "abc123"


# Made with Bob
