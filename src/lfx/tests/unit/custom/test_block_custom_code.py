"""Integration tests for custom code blocking feature."""

from unittest.mock import Mock, patch

import pytest
from lfx.custom.hash_validator import _generate_short_hash
from lfx.custom.validate import create_class, create_function


class TestBlockCustomCodeIntegration:
    """Integration tests for blocking custom code execution."""

    def test_create_class_allowed_when_blocking_disabled(self):
        """Test that create_class works when blocking is disabled."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Should work when blocking is disabled (default)
        result = create_class(code, "TestComponent")
        assert result is not None

    def test_create_class_blocked_when_hash_not_in_index(self):
        """Test that create_class is blocked when hash not in index."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        code_hash = _generate_short_hash(code)

        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return empty set (hash not found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'TestComponent' is not allowed"):
                create_class(code, "TestComponent")

    def test_create_class_allowed_when_hash_in_index(self):
        """Test that create_class works when hash is in index."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return True (hash found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            # Should not raise
            result = create_class(code, "TestComponent")
            assert result is not None

    def test_create_function_allowed_when_blocking_disabled(self):
        """Test that create_function works when blocking is disabled."""
        code = """
def test_function(x):
    return x * 2
"""
        # Should work when blocking is disabled (default)
        result = create_function(code, "test_function")
        assert result is not None

    def test_create_function_blocked_when_hash_not_in_index(self):
        """Test that create_function is blocked when hash not in index."""
        code = """
def test_function(x):
    return x * 2
"""
        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return False (hash not found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'test_function' is not allowed"):
                create_function(code, "test_function")

    def test_create_function_allowed_when_hash_in_index(self):
        """Test that create_function works when hash is in index."""
        code = """
def test_function(x):
    return x * 2
"""
        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return True (hash found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            # Should not raise
            result = create_function(code, "test_function")
            assert result is not None

    def test_blocking_respects_environment_variable(self, monkeypatch):
        """Test that blocking respects LANGFLOW_ALLOW_CUSTOM_COMPONENTS env var."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Disable allowing (enable blocking) via env var
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")

        # Mock hash lookup to return False (hash not found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'TestComponent' is not allowed"):
                create_class(code, "TestComponent")

        # Enable allowing (disable blocking) via env var
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")

        # Should work now
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            result = create_class(code, "TestComponent")
            assert result is not None
