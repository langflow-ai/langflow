"""Tests for hash validator module."""

import hashlib
from unittest.mock import Mock, patch

import orjson
from lfx.custom.hash_validator import (
    _extract_hashes_from_index,
    _generate_full_hash,
    _generate_short_hash,
    is_code_hash_allowed,
)


class TestHashGeneration:
    """Tests for hash generation functions."""

    def test_generate_full_hash(self):
        """Test full hash generation."""
        code = "class TestComponent:\n    pass"
        hash_result = _generate_full_hash(code)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex digest is 64 chars
        # Verify it's deterministic
        assert _generate_full_hash(code) == hash_result

    def test_generate_short_hash(self):
        """Test short hash generation."""
        code = "class TestComponent:\n    pass"
        hash_result = _generate_short_hash(code)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 12  # First 12 chars
        # Verify it matches first 12 chars of full hash
        full_hash = _generate_full_hash(code)
        assert hash_result == full_hash[:12]

    def test_hash_different_code_different_hash(self):
        """Test that different code produces different hashes."""
        code1 = "class TestComponent1:\n    pass"
        code2 = "class TestComponent2:\n    pass"
        hash1 = _generate_short_hash(code1)
        hash2 = _generate_short_hash(code2)
        assert hash1 != hash2

    def test_hash_same_code_same_hash(self):
        """Test that same code produces same hash."""
        code = "class TestComponent:\n    pass"
        hash1 = _generate_short_hash(code)
        hash2 = _generate_short_hash(code)
        assert hash1 == hash2


class TestExtractHashesFromIndex:
    """Tests for extracting hashes from component index."""

    def test_extract_hashes_simple(self):
        """Test extracting hashes from a simple index."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "metadata": {"code_hash": "abc123def456"},
                        },
                        "Component2": {
                            "metadata": {"code_hash": "def456ghi789"},
                        },
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "abc123def456" in hashes
        assert "def456ghi789" in hashes
        assert len(hashes) == 2

    def test_extract_hashes_multiple_categories(self):
        """Test extracting hashes from multiple categories."""
        index = {
            "entries": [
                ["Category1", {"Comp1": {"metadata": {"code_hash": "hash1"}}}],
                ["Category2", {"Comp2": {"metadata": {"code_hash": "hash2"}}}],
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "hash1" in hashes
        assert "hash2" in hashes
        assert len(hashes) == 2

    def test_extract_hashes_missing_metadata(self):
        """Test extracting hashes when metadata is missing."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {"display_name": "Test"},  # No metadata
                        "Component2": {"metadata": {"code_hash": "hash1"}},
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "hash1" in hashes
        assert len(hashes) == 1

    def test_extract_hashes_missing_code_hash(self):
        """Test extracting hashes when code_hash is missing."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {"metadata": {"other_field": "value"}},  # No code_hash
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert len(hashes) == 0

    def test_extract_hashes_empty_index(self):
        """Test extracting hashes from empty index."""
        index = {"entries": []}
        hashes = _extract_hashes_from_index(index)
        assert len(hashes) == 0

    def test_extract_hashes_no_entries(self):
        """Test extracting hashes when entries key is missing."""
        index = {}
        hashes = _extract_hashes_from_index(index)
        assert len(hashes) == 0

    def test_extract_hashes_includes_hash_history(self):
        """Test that hashes from hash_history are also extracted."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "metadata": {
                                "code_hash": "current_hash",
                                "hash_history": [
                                    {"hash": "old_hash_1", "v_from": "1.0.0", "v_to": "1.1.0"},
                                    {"hash": "old_hash_2", "v_from": "1.1.0", "v_to": "1.2.0"},
                                ],
                            },
                        },
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "current_hash" in hashes
        assert "old_hash_1" in hashes
        assert "old_hash_2" in hashes
        assert len(hashes) == 3

    def test_extract_hashes_hash_history_only_current(self):
        """Test extraction when component has current hash but no history."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "metadata": {
                                "code_hash": "current_hash",
                                "hash_history": [],  # Empty history
                            },
                        },
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "current_hash" in hashes
        assert len(hashes) == 1

    def test_extract_hashes_hash_history_no_duplicates(self):
        """Test that duplicate hashes in history are deduplicated."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "metadata": {
                                "code_hash": "same_hash",
                                "hash_history": [
                                    {"hash": "same_hash", "v_from": "1.0.0", "v_to": "1.1.0"},
                                    {"hash": "same_hash", "v_from": "1.1.0", "v_to": "1.2.0"},
                                ],
                            },
                        },
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "same_hash" in hashes
        assert len(hashes) == 1  # Should be deduplicated

    def test_extract_hashes_hash_history_multiple_components(self):
        """Test extraction from multiple components with hash histories."""
        index = {
            "entries": [
                [
                    "Category1",
                    {
                        "Comp1": {
                            "metadata": {
                                "code_hash": "comp1_current",
                                "hash_history": [{"hash": "comp1_old", "v_from": "1.0.0", "v_to": "1.1.0"}],
                            },
                        },
                    },
                ],
                [
                    "Category2",
                    {
                        "Comp2": {
                            "metadata": {
                                "code_hash": "comp2_current",
                                "hash_history": [{"hash": "comp2_old", "v_from": "1.0.0", "v_to": "1.1.0"}],
                            },
                        },
                    },
                ],
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "comp1_current" in hashes
        assert "comp1_old" in hashes
        assert "comp2_current" in hashes
        assert "comp2_old" in hashes
        assert len(hashes) == 4

    def test_extract_hashes_hash_history_malformed_entries(self):
        """Test that malformed hash_history entries are skipped gracefully."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "metadata": {
                                "code_hash": "current_hash",
                                "hash_history": [
                                    {"hash": "valid_hash", "v_from": "1.0.0", "v_to": "1.1.0"},
                                    {"no_hash_key": "invalid"},  # Missing 'hash' key
                                    "not_a_dict",  # Not a dict
                                    {"hash": "", "v_from": "1.0.0", "v_to": "1.1.0"},  # Empty hash
                                    {"hash": None, "v_from": "1.0.0", "v_to": "1.1.0"},  # None hash
                                ],
                            },
                        },
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "current_hash" in hashes
        assert "valid_hash" in hashes
        assert len(hashes) == 2  # Only valid hashes

    def test_extract_hashes_hash_history_not_a_list(self):
        """Test that non-list hash_history is handled gracefully."""
        index = {
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "metadata": {
                                "code_hash": "current_hash",
                                "hash_history": "not_a_list",  # Invalid type
                            },
                        },
                    },
                ]
            ]
        }
        hashes = _extract_hashes_from_index(index)
        assert "current_hash" in hashes
        assert len(hashes) == 1  # Should still get current hash


class TestIsCodeHashAllowed:
    """Tests for is_code_hash_allowed function."""

    def test_allowed_when_allowed_enabled(self):
        """Test that code is allowed when allow_custom_components is True."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = True

        code = "class TestComponent:\n    pass"
        assert is_code_hash_allowed(code, mock_settings) is True

    def test_blocked_when_hash_not_in_index(self):
        """Test that code is blocked when hash not in index."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock the hash loading to return empty set
        with patch("lfx.custom.hash_validator._get_cached_hashes", return_value=set()):
            code = "class TestComponent:\n    pass"
            assert is_code_hash_allowed(code, mock_settings) is False

    def test_allowed_when_hash_in_index(self):
        """Test that code is allowed when hash is in index."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        code = "class TestComponent:\n    pass"
        code_hash = _generate_short_hash(code)

        # Mock the hash loading to return set with our hash
        with patch("lfx.custom.hash_validator._get_cached_hashes", return_value={code_hash}):
            assert is_code_hash_allowed(code, mock_settings) is True

    def test_allowed_when_no_settings_service(self):
        """Test that code is allowed when settings service is None."""
        code = "class TestComponent:\n    pass"
        # Should default to allowing code when no settings service
        assert is_code_hash_allowed(code, None) is True

    def test_allowed_when_settings_service_unavailable(self):
        """Test that code is allowed when settings service can't be fetched."""
        code = "class TestComponent:\n    pass"
        with patch("lfx.services.deps.get_settings_service", side_effect=Exception("Service unavailable")):
            # Should default to allowing code when service unavailable
            assert is_code_hash_allowed(code) is True

    def test_empty_code_allowed(self):
        """Test that empty code is allowed."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False
        assert is_code_hash_allowed("", mock_settings) is True
        assert is_code_hash_allowed("   ", mock_settings) is True
        assert is_code_hash_allowed("\n\n\t  \n", mock_settings) is True

    def test_hash_generation_error_allows_code(self):
        """Test that hash generation errors allow code (fail open)."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash generation to raise an error
        with patch("lfx.custom.hash_validator._generate_short_hash", side_effect=Exception("Hash error")):
            code = "class TestComponent:\n    pass"
            # Should allow code when hash generation fails
            assert is_code_hash_allowed(code, mock_settings) is True

    def test_index_loading_error_allows_code(self):
        """Test that index loading errors allow code (fail open)."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock index loading to raise an error
        with patch("lfx.custom.hash_validator._get_cached_hashes", side_effect=Exception("Index error")):
            code = "class TestComponent:\n    pass"
            # Should allow code when index loading fails
            assert is_code_hash_allowed(code, mock_settings) is True

    def test_malformed_index_handled_gracefully(self):
        """Test that malformed index is handled gracefully."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock index with malformed data
        with patch("lfx.custom.hash_validator._get_cached_hashes", return_value=set()):
            code = "class TestComponent:\n    pass"
            # Should block when index is empty (malformed or no hashes)
            assert is_code_hash_allowed(code, mock_settings) is False

    def test_cache_behavior(self):
        """Test that cache works correctly with same settings."""
        code = "class TestComponent:\n    pass"
        code_hash = _generate_short_hash(code)

        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False
        mock_settings.settings.components_index_path = None

        # Mock the internal cache mechanism by patching _get_cached_hashes
        # to track how many times _load_component_index_hashes is called
        with patch("lfx.custom.hash_validator._load_component_index_hashes") as mock_load:
            mock_load.return_value = {code_hash}

            # First call should load
            assert is_code_hash_allowed(code, mock_settings) is True
            first_call_count = mock_load.call_count

            # Second call with same settings should use cache (no additional load)
            assert is_code_hash_allowed(code, mock_settings) is True
            # Verify load was only called once (cache was used)
            assert mock_load.call_count == first_call_count

    def test_cache_invalidation_on_settings_change(self):
        """Test that cache is invalidated when settings change."""
        code = "class TestComponent:\n    pass"
        code_hash = _generate_short_hash(code)

        # Create first settings with one path
        mock_settings1 = Mock()
        mock_settings1.settings.allow_custom_components = False
        mock_settings1.settings.components_index_path = "/path/to/index1.json"

        # Create second settings with different path
        mock_settings2 = Mock()
        mock_settings2.settings.allow_custom_components = False
        mock_settings2.settings.components_index_path = "/path/to/index2.json"

        # Mock _load_component_index_hashes to track calls
        with patch("lfx.custom.hash_validator._load_component_index_hashes") as mock_load:
            mock_load.return_value = {code_hash}

            # Call with first settings - should load
            assert is_code_hash_allowed(code, mock_settings1) is True
            assert mock_load.call_count == 1

            # Call again with same settings - should use cache (no additional load)
            assert is_code_hash_allowed(code, mock_settings1) is True
            assert mock_load.call_count == 1  # Still 1, cache was used

            # Call with different settings - should invalidate cache and reload
            assert is_code_hash_allowed(code, mock_settings2) is True
            assert mock_load.call_count == 2  # Reloaded due to different settings


class TestIntegrationWithComponentIndex:
    """Integration tests with actual component index structure."""

    def test_with_real_index_structure(self):
        """Test with a structure similar to real component index."""
        # Create a mock index file
        index_data = {
            "version": "1.0.0",
            "metadata": {"num_components": 2},
            "entries": [
                [
                    "TestCategory",
                    {
                        "Component1": {
                            "display_name": "Component 1",
                            "metadata": {"code_hash": "abc123def456"},
                        },
                        "Component2": {
                            "display_name": "Component 2",
                            "metadata": {"code_hash": "def456ghi789"},
                        },
                    },
                ]
            ],
        }

        # Calculate hash for integrity
        tmp = dict(index_data)
        payload = orjson.dumps(tmp, option=orjson.OPT_SORT_KEYS)
        index_data["sha256"] = hashlib.sha256(payload).hexdigest()

        # Test extraction
        hashes = _extract_hashes_from_index(index_data)
        assert "abc123def456" in hashes
        assert "def456ghi789" in hashes
        assert len(hashes) == 2
