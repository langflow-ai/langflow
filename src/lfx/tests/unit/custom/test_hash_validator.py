"""Tests for hash validator module."""

from unittest.mock import Mock, patch

import pytest
from lfx.custom.hash_validator import (
    _extract_hashes_from_history,
    _generate_code_hash,
    is_code_hash_allowed,
)


class TestHashGeneration:
    """Tests for hash generation functions."""

    def test_generate_code_hash(self):
        """Test code hash generation (12 char SHA256)."""
        code = "class TestComponent:\n    pass"
        hash_result = _generate_code_hash(code)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 12  # First 12 chars of SHA256
        # Verify it's deterministic
        assert _generate_code_hash(code) == hash_result

    def test_generate_code_hash_empty_raises(self):
        """Test that empty code raises ValueError."""
        with pytest.raises(ValueError, match="Empty source code"):
            _generate_code_hash("")

    def test_generate_code_hash_non_string_raises(self):
        """Test that non-string input raises TypeError."""
        with pytest.raises(TypeError, match="Source code must be a string"):
            _generate_code_hash(None)  # type: ignore

    def test_hash_different_code_different_hash(self):
        """Test that different code produces different hashes."""
        code1 = "class TestComponent1:\n    pass"
        code2 = "class TestComponent2:\n    pass"
        hash1 = _generate_code_hash(code1)
        hash2 = _generate_code_hash(code2)
        assert hash1 != hash2

    def test_hash_same_code_same_hash(self):
        """Test that same code produces same hash."""
        code = "class TestComponent:\n    pass"
        hash1 = _generate_code_hash(code)
        hash2 = _generate_code_hash(code)
        assert hash1 == hash2


class TestExtractHashesFromHistory:
    """Tests for extracting hashes from hash history."""

    def test_extract_hashes_simple(self):
        """Test extracting hashes from a simple history (old string format)."""
        history = {
            "Component1": {
                "versions": {
                    "0.3.0": "abc123def456",
                }
            },
            "Component2": {
                "versions": {
                    "0.3.0": "def456ghi789",
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert "abc123def456" in allowed_hashes
        assert "def456ghi789" in allowed_hashes
        assert len(allowed_hashes) == 2
        assert len(code_exec_hashes) == 0  # No code execution components

    def test_extract_hashes_multiple_versions(self):
        """Test extracting hashes from components with multiple versions."""
        history = {
            "Component1": {
                "versions": {
                    "0.1.0": "hash1_v1",
                    "0.2.0": "hash1_v2",
                    "0.3.0": "hash1_v3",
                }
            },
            "Component2": {
                "versions": {
                    "0.3.0": "hash2_v1",
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert "hash1_v1" in allowed_hashes
        assert "hash1_v2" in allowed_hashes
        assert "hash1_v3" in allowed_hashes
        assert "hash2_v1" in allowed_hashes
        assert len(allowed_hashes) == 4
        assert len(code_exec_hashes) == 0

    def test_extract_hashes_missing_versions_raises(self):
        """Test that missing versions key raises ValueError."""
        history = {
            "Component1": {
                "other_field": "value"  # No versions
            },
        }
        try:
            _extract_hashes_from_history(history)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing 'versions' key" in str(e)
            assert "Component1" in str(e)

    def test_extract_hashes_empty_versions(self):
        """Test extracting hashes when versions dict is empty (valid case)."""
        history = {
            "Component1": {
                "versions": {}  # Empty versions - valid but no hashes
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert len(allowed_hashes) == 0
        assert len(code_exec_hashes) == 0

    def test_extract_hashes_empty_history(self):
        """Test extracting hashes from empty history."""
        history = {}
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert len(allowed_hashes) == 0
        assert len(code_exec_hashes) == 0

    def test_extract_hashes_none_history(self):
        """Test extracting hashes when history is None."""
        history = None
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert len(allowed_hashes) == 0
        assert len(code_exec_hashes) == 0

    def test_extract_hashes_no_duplicates(self):
        """Test that duplicate hashes across versions are deduplicated."""
        history = {
            "Component1": {
                "versions": {
                    "0.1.0": "same_hash",
                    "0.2.0": "same_hash",
                    "0.3.0": "same_hash",
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert "same_hash" in allowed_hashes
        assert len(allowed_hashes) == 1  # Should be deduplicated
        assert len(code_exec_hashes) == 0

    def test_extract_hashes_multiple_components_multiple_versions(self):
        """Test extraction from multiple components with multiple versions."""
        history = {
            "Comp1": {
                "versions": {
                    "0.1.0": "comp1_v1",
                    "0.2.0": "comp1_v2",
                }
            },
            "Comp2": {
                "versions": {
                    "0.1.0": "comp2_v1",
                    "0.2.0": "comp2_v2",
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert "comp1_v1" in allowed_hashes
        assert "comp1_v2" in allowed_hashes
        assert "comp2_v1" in allowed_hashes
        assert "comp2_v2" in allowed_hashes
        assert len(allowed_hashes) == 4
        assert len(code_exec_hashes) == 0

    def test_extract_hashes_empty_hash_raises(self):
        """Test that empty hash raises ValueError."""
        history = {
            "Component1": {
                "versions": {
                    "0.1.0": "valid_hash",
                    "0.2.0": "",  # Empty hash
                }
            },
        }
        try:
            _extract_hashes_from_history(history)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Empty hash" in str(e)
            assert "Component1" in str(e)
            assert "0.2.0" in str(e)

    def test_extract_hashes_none_hash_raises(self):
        """Test that None hash raises ValueError."""
        history = {
            "Component1": {
                "versions": {
                    "0.1.0": None,  # None hash
                }
            },
        }
        try:
            _extract_hashes_from_history(history)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid version data type" in str(e)
            assert "Component1" in str(e)

    def test_extract_hashes_component_not_dict_raises(self):
        """Test that non-dict component data raises ValueError."""
        history = {
            "Component1": "not_a_dict",  # Not a dict
        }
        try:
            _extract_hashes_from_history(history)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid component data format" in str(e)
            assert "Component1" in str(e)

    def test_extract_hashes_versions_not_a_dict_raises(self):
        """Test that non-dict versions raises ValueError."""
        history = {
            "Component1": {
                "versions": "not_a_dict",  # Invalid type
            },
        }
        try:
            _extract_hashes_from_history(history)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid versions format" in str(e)
            assert "Component1" in str(e)

    def test_extract_hashes_new_dict_format(self):
        """Test extracting hashes from new dict format with executes_code flag."""
        history = {
            "Component1": {
                "versions": {
                    "0.3.0": {"hash": "abc123def456", "executes_code": False},
                }
            },
            "Component2": {
                "versions": {
                    "0.3.0": {"hash": "def456ghi789", "executes_code": True},
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history, allow_code_execution=True)
        assert "abc123def456" in allowed_hashes
        assert "def456ghi789" in allowed_hashes
        assert len(allowed_hashes) == 2
        assert "def456ghi789" in code_exec_hashes
        assert len(code_exec_hashes) == 1

    def test_extract_hashes_mixed_formats(self):
        """Test extracting hashes from mixed old and new formats."""
        history = {
            "OldComponent": {
                "versions": {
                    "0.1.0": "old_hash_123",  # Old string format
                }
            },
            "NewComponent": {
                "versions": {
                    "0.3.0": {"hash": "new_hash_456", "executes_code": False},  # New dict format
                }
            },
            "CodeExecComponent": {
                "versions": {
                    "0.3.0": {"hash": "code_hash_789", "executes_code": True},  # Code execution
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history, allow_code_execution=True)
        assert "old_hash_123" in allowed_hashes
        assert "new_hash_456" in allowed_hashes
        assert "code_hash_789" in allowed_hashes
        assert len(allowed_hashes) == 3
        assert "code_hash_789" in code_exec_hashes
        assert len(code_exec_hashes) == 1

    def test_extract_hashes_filter_code_execution(self):
        """Test that code execution components are filtered when allow_code_execution=False."""
        history = {
            "NormalComponent": {
                "versions": {
                    "0.3.0": {"hash": "normal_hash", "executes_code": False},
                }
            },
            "CodeExecComponent": {
                "versions": {
                    "0.3.0": {"hash": "code_hash", "executes_code": True},
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history, allow_code_execution=False)
        assert "normal_hash" in allowed_hashes
        assert "code_hash" not in allowed_hashes  # Should be filtered out
        assert len(allowed_hashes) == 1
        assert "code_hash" in code_exec_hashes  # Still tracked separately
        assert len(code_exec_hashes) == 1

    def test_extract_hashes_multiple_code_exec_components(self):
        """Test handling multiple code execution components."""
        history = {
            "PythonREPL": {
                "versions": {
                    "0.3.0": {"hash": "repl_hash", "executes_code": True},
                }
            },
            "LambdaFilter": {
                "versions": {
                    "0.3.0": {"hash": "lambda_hash", "executes_code": True},
                }
            },
            "NormalComponent": {
                "versions": {
                    "0.3.0": {"hash": "normal_hash", "executes_code": False},
                }
            },
        }
        # With code execution allowed
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history, allow_code_execution=True)
        assert len(allowed_hashes) == 3
        assert len(code_exec_hashes) == 2

        # With code execution blocked
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history, allow_code_execution=False)
        assert len(allowed_hashes) == 1  # Only normal component
        assert "normal_hash" in allowed_hashes
        assert len(code_exec_hashes) == 2  # Both code exec components tracked

    def test_extract_hashes_dict_format_missing_hash_key(self):
        """Test that dict format without 'hash' key raises ValueError."""
        history = {
            "Component1": {
                "versions": {
                    "0.3.0": {"executes_code": True},  # Missing 'hash' key
                }
            },
        }
        try:
            _extract_hashes_from_history(history)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing 'hash' key" in str(e)
            assert "Component1" in str(e)

    def test_extract_hashes_dict_format_defaults_executes_code_false(self):
        """Test that dict format without executes_code defaults to False."""
        history = {
            "Component1": {
                "versions": {
                    "0.3.0": {"hash": "test_hash"},  # No executes_code key
                }
            },
        }
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history)
        assert "test_hash" in allowed_hashes
        assert len(code_exec_hashes) == 0  # Should default to False


class TestIsCodeHashAllowed:
    """Tests for is_code_hash_allowed function."""

    def test_allowed_when_allowed_enabled(self):
        """Test that code is allowed when allow_custom_components is True."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = True

        code = "class TestComponent:\n    pass"
        assert is_code_hash_allowed(code, mock_settings) is True

    def test_blocked_when_hash_not_in_history(self):
        """Test that code is blocked when hash not in history."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock the hash loading to return empty set
        with patch("lfx.custom.hash_validator._get_cached_hashes", return_value=set()):
            code = "class TestComponent:\n    pass"
            assert is_code_hash_allowed(code, mock_settings) is False

    def test_allowed_when_hash_in_history(self):
        """Test that code is allowed when hash is in history."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        code = "class TestComponent:\n    pass"
        code_hash = _generate_code_hash(code)

        # Mock the hash loading to return set with our hash
        with patch("lfx.custom.hash_validator._get_cached_hashes", return_value={code_hash}):
            assert is_code_hash_allowed(code, mock_settings) is True

    def test_raises_when_no_settings_service(self):
        """Test that an exception is raised when settings service is None."""
        code = "class TestComponent:\n    pass"
        # Should raise ValueError when no settings service (fail fast)
        with patch("lfx.custom.hash_validator.get_settings_service", return_value=None):
            try:
                is_code_hash_allowed(code)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "Settings service is not available" in str(e)

    def test_raises_when_settings_service_unavailable(self):
        """Test that an exception is raised when settings service can't be fetched."""
        code = "class TestComponent:\n    pass"
        with patch("lfx.custom.hash_validator.get_settings_service", side_effect=Exception("Service unavailable")):
            # Should raise exception when service unavailable (fail fast)
            try:
                is_code_hash_allowed(code)
                assert False, "Should have raised Exception"
            except Exception as e:
                assert "Service unavailable" in str(e)

    def test_empty_code_allowed(self):
        """Test that empty code is allowed."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False
        assert is_code_hash_allowed("", mock_settings) is True
        assert is_code_hash_allowed("   ", mock_settings) is True
        assert is_code_hash_allowed("\n\n\t  \n", mock_settings) is True

    def test_hash_generation_error_raises(self):
        """Test that hash generation errors raise exceptions (fail fast)."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash generation to raise an error
        with patch("lfx.custom.hash_validator._generate_code_hash", side_effect=Exception("Hash error")):
            code = "class TestComponent:\n    pass"
            # Should raise exception when hash generation fails (fail fast)
            try:
                is_code_hash_allowed(code, mock_settings)
                assert False, "Should have raised Exception"
            except Exception as e:
                assert "Hash error" in str(e)

    def test_history_loading_error_raises(self):
        """Test that history loading errors raise exceptions (fail fast)."""
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock history loading to raise an error
        with patch("lfx.custom.hash_validator._get_cached_hashes", side_effect=ValueError("History error")):
            code = "class TestComponent:\n    pass"
            # Should raise exception when history loading fails (fail fast)
            try:
                is_code_hash_allowed(code, mock_settings)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "History error" in str(e)

    def test_empty_history_raises(self):
        """Test that empty hash history raises ValueError."""
        from lfx.custom.hash_validator import _load_hash_history

        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False
        mock_settings.settings.allow_nightly_core_components = False

        # Mock Path.exists to return True but read_bytes to return empty history
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.read_bytes", return_value=b"{}"):
            # Should raise ValueError when history is empty (critical error)
            try:
                _load_hash_history(mock_settings)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "No hashes loaded" in str(e)

    def test_cache_behavior(self):
        """Test that cache works correctly with same settings."""
        code = "class TestComponent:\n    pass"
        code_hash = _generate_code_hash(code)

        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock the internal cache mechanism by patching _get_cached_hashes
        # to track how many times _load_hash_history is called
        with patch("lfx.custom.hash_validator._load_hash_history") as mock_load:
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
        code_hash = _generate_code_hash(code)

        # Create first settings
        mock_settings1 = Mock()
        mock_settings1.settings.allow_custom_components = False

        # Create second settings (different object)
        mock_settings2 = Mock()
        mock_settings2.settings.allow_custom_components = False

        # Mock _load_hash_history to track calls
        with patch("lfx.custom.hash_validator._load_hash_history") as mock_load:
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

    def test_cache_invalidation_on_code_execution_setting_change(self):
        """Test that cache is invalidated when allow_code_execution_components changes."""
        code = "class TestComponent:\n    pass"
        code_hash = _generate_code_hash(code)

        # Create settings with code execution allowed
        mock_settings1 = Mock()
        mock_settings1.settings.allow_custom_components = False
        mock_settings1.settings.allow_nightly_core_components = False
        mock_settings1.settings.allow_code_execution_components = True

        # Create settings with code execution blocked
        mock_settings2 = Mock()
        mock_settings2.settings.allow_custom_components = False
        mock_settings2.settings.allow_nightly_core_components = False
        mock_settings2.settings.allow_code_execution_components = False

        # Mock _load_hash_history to track calls
        with patch("lfx.custom.hash_validator._load_hash_history") as mock_load:
            mock_load.return_value = {code_hash}

            # Call with code execution allowed - should load
            assert is_code_hash_allowed(code, mock_settings1) is True
            assert mock_load.call_count == 1

            # Call again with same settings - should use cache
            assert is_code_hash_allowed(code, mock_settings1) is True
            assert mock_load.call_count == 1  # Still 1, cache was used

            # Call with code execution blocked - should invalidate cache and reload
            assert is_code_hash_allowed(code, mock_settings2) is True
            assert mock_load.call_count == 2  # Reloaded due to different setting


class TestIntegrationWithHashHistory:
    """Integration tests with actual hash history structure."""

    def test_with_real_history_structure(self):
        """Test with a structure similar to real hash history."""
        # Create a mock history file
        history_data = {
            "Component1": {
                "versions": {
                    "0.3.0": "abc123def456",
                }
            },
            "Component2": {
                "versions": {
                    "0.2.0": "old_hash_123",
                    "0.3.0": "def456ghi789",
                }
            },
        }

        # Test extraction - now returns tuple
        allowed_hashes, code_exec_hashes = _extract_hashes_from_history(history_data)
        assert "abc123def456" in allowed_hashes
        assert "def456ghi789" in allowed_hashes
        assert "old_hash_123" in allowed_hashes
        assert len(allowed_hashes) == 3
        assert len(code_exec_hashes) == 0  # No code execution components
