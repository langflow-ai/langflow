"""Unit tests for the _import_utils module.

Tests the core import_mod function used throughout the dynamic import system.
"""

from unittest.mock import Mock, patch

import pytest
from langflow.components._importing import import_mod


class TestImportAttr:
    """Test the import_mod utility function in detail."""

    def test_import_module_with_none_module_name(self):
        """Test importing a module when module_name is None."""
        # This should import the module directly using the attr_name
        result = import_mod("agents", None, "langflow.components")

        # Should return the agents module
        assert result is not None
        assert hasattr(result, "__all__")

    def test_import_module_with_module_name(self):
        """Test importing a module when module_name is __module__."""
        # This should import the module directly using the attr_name
        result = import_mod("agents", "__module__", "langflow.components")

        # Should return the agents module
        assert result is not None
        assert hasattr(result, "__all__")

    def test_import_modibute_from_module(self):
        """Test importing a specific attribute from a module."""
        # Test importing a class from a specific module
        result = import_mod("AnthropicModelComponent", "anthropic", "langflow.components.anthropic")

        assert result is not None
        assert hasattr(result, "__name__")
        assert "Component" in result.__name__

    def test_import_nonexistent_module(self):
        """Test error handling when module doesn't exist."""
        with pytest.raises(ImportError, match="not found"):
            import_mod("SomeComponent", "nonexistent_module", "langflow.components.openai")

    def test_import_nonexistent_attribute(self):
        """Test error handling when attribute doesn't exist in module."""
        with pytest.raises(AttributeError):
            import_mod("NonExistentComponent", "anthropic", "langflow.components.anthropic")

    def test_import_with_none_package(self):
        """Test behavior when package is None."""
        # This should raise TypeError because relative imports require a package
        with pytest.raises(TypeError, match="package.*required"):
            import_mod("something", "some_module", None)

    @patch("langflow.components._import_utils.import_module")
    def test_module_not_found_error_handling(self, mock_import_module):
        """Test specific ModuleNotFoundError handling."""
        mock_import_module.side_effect = ModuleNotFoundError("No module named 'test'")

        with pytest.raises(ImportError, match="not found"):
            import_mod("TestComponent", "test_module", "test.package")

    @patch("langflow.components._import_utils.import_module")
    def test_getattr_error_handling(self, mock_import_module):
        """Test AttributeError handling when getting attribute from module."""
        # Mock module that doesn't have the requested attribute
        mock_module = Mock()
        del mock_module.TestComponent  # Ensure attribute doesn't exist
        mock_import_module.return_value = mock_module

        with pytest.raises(AttributeError):
            import_mod("TestComponent", "test_module", "test.package")

    def test_relative_import_behavior(self):
        """Test that relative imports are constructed correctly."""
        # This test verifies the relative import logic
        result = import_mod("helpers", "__module__", "langflow.components")
        assert result is not None

    def test_package_resolution(self):
        """Test that package parameter is used correctly."""
        # Test with a known working package and module
        result = import_mod("CalculatorComponent", "calculator_core", "langflow.components.helpers")
        assert result is not None
        assert callable(result)

    def test_import_mod_with_special_module_name(self):
        """Test behavior with special module_name values."""
        # Test with "__module__" - should import the attr_name as a module
        result = import_mod("data", "__module__", "langflow.components")
        assert result is not None

        # Test with None - should also import the attr_name as a module
        result2 = import_mod("data", None, "langflow.components")
        assert result2 is not None

    def test_error_message_formatting(self):
        """Test that error messages are properly formatted."""
        with pytest.raises(ImportError) as exc_info:
            import_mod("NonExistent", "nonexistent", "langflow.components")

        error_msg = str(exc_info.value)
        assert "langflow.components" in error_msg
        assert "nonexistent" in error_msg

    def test_return_value_types(self):
        """Test that import_mod returns appropriate types."""
        # Test module import
        module_result = import_mod("openai", "__module__", "langflow.components")
        assert hasattr(module_result, "__name__")

        # Test class import
        class_result = import_mod("OpenAIModelComponent", "openai_chat_model", "langflow.components.openai")
        assert callable(class_result)
        assert hasattr(class_result, "__name__")

    def test_caching_independence(self):
        """Test that import_mod doesn't interfere with Python's module caching."""
        # Multiple calls should work consistently
        result1 = import_mod("agents", "__module__", "langflow.components")
        result2 = import_mod("agents", "__module__", "langflow.components")

        # Should return the same module object (Python's import caching)
        assert result1 is result2


class TestImportAttrEdgeCases:
    """Test edge cases and boundary conditions for import_mod."""

    def test_empty_strings(self):
        """Test behavior with empty strings."""
        with pytest.raises((ImportError, ValueError)):
            import_mod("", "module", "package")

        with pytest.raises((ImportError, ValueError)):
            import_mod("attr", "", "package")

    def test_whitespace_handling(self):
        """Test that whitespace in names is handled appropriately."""
        with pytest.raises(ImportError):
            import_mod("attr name", "module", "package")

    def test_special_characters(self):
        """Test handling of special characters in names."""
        with pytest.raises((ImportError, ValueError)):
            import_mod("attr-name", "module", "package")

    def test_unicode_names(self):
        """Test handling of unicode characters in names."""
        with pytest.raises(ImportError):
            import_mod("attß", "module", "package")

    def test_very_long_names(self):
        """Test handling of very long module/attribute names."""
        long_name = "a" * 1000
        with pytest.raises(ImportError):
            import_mod(long_name, "module", "package")

    def test_numeric_names(self):
        """Test handling of numeric names."""
        with pytest.raises(ImportError):
            import_mod("123", "module", "package")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
