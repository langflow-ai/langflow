"""Integration tests for custom code blocking feature."""

from unittest.mock import Mock, patch

import pytest
from lfx.custom.validate import create_class, create_function, extract_display_name


class TestExtractDisplayName:
    """Unit tests for extract_display_name function."""

    def test_extract_display_name_simple(self):
        """Test extracting display_name from a simple component."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test Component"
"""
        result = extract_display_name(code)
        assert result == "Test Component"

    def test_extract_display_name_with_other_attributes(self):
        """Test extracting display_name when other attributes are present."""
        code = """
from lfx.custom import Component

class MyComponent(Component):
    description = "A test component"
    display_name = "My Custom Component"
    icon = "icon.svg"
"""
        result = extract_display_name(code)
        assert result == "My Custom Component"

    def test_extract_display_name_no_display_name(self):
        """Test that None is returned when display_name is not present."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    description = "A test component"
"""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_not_a_component(self):
        """Test that None is returned for non-Component classes."""
        code = """
class RegularClass:
    display_name = "Not a Component"
"""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_multiple_classes(self):
        """Test extracting display_name from first Component subclass."""
        code = """
from lfx.custom import Component

class FirstComponent(Component):
    display_name = "First Component"

class SecondComponent(Component):
    display_name = "Second Component"
"""
        result = extract_display_name(code)
        assert result == "First Component"

    def test_extract_display_name_with_docstring(self):
        """Test extracting display_name when class has docstring."""
        code = '''
from lfx.custom import Component

class TestComponent(Component):
    """This is a test component."""
    display_name = "Test Component"
    
    def build(self):
        pass
'''
        result = extract_display_name(code)
        assert result == "Test Component"

    def test_extract_display_name_invalid_syntax(self):
        """Test that None is returned for invalid Python syntax."""
        code = "this is not valid python code {"
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_empty_string(self):
        """Test that None is returned for empty string."""
        code = ""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_with_f_string(self):
        """Test extracting display_name when it's an f-string (should return None)."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = f"Dynamic {name}"
"""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_nested_in_body(self):
        """Test extracting display_name from class body assignments."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    def __init__(self):
        self.display_name = "Should Not Extract This"
    
    display_name = "Correct Display Name"
"""
        result = extract_display_name(code)
        assert result == "Correct Display Name"

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
        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return empty set (hash not found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'Test' is not allowed"):
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
            with pytest.raises(ValueError, match="Custom Component 'Test' is not allowed"):
                create_class(code, "TestComponent")

        # Enable allowing (disable blocking) via env var
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")

        # Should work now
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            result = create_class(code, "TestComponent")
            assert result is not None
