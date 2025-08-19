"""Tests for dynamic import refactor in langflow components.

This module tests the new langchain-style dynamic import system to ensure:
1. Lazy loading works correctly
2. Components are imported only when accessed
3. Caching works properly
4. Error handling for missing components
5. __dir__ functionality for IDE autocomplete
6. Backward compatibility with existing imports
"""

from unittest.mock import patch

import pytest

from lfx.components._importing import import_mod


class TestImportUtils:
    """Test the import_mod utility function."""

    def test_import_mod_with_module_name(self):
        """Test importing specific attribute from a module."""
        # Test importing a specific class from a module
        result = import_mod("CalculatorComponent", "calculator_core", "lfx.components.helpers")
        assert result is not None
        assert hasattr(result, "__name__")
        assert "Calculator" in result.__name__

    def test_import_mod_without_module_name(self):
        """Test importing entire module when module_name is None."""
        result = import_mod("agents", "__module__", "lfx.components")
        assert result is not None
        # Should return the agents module
        assert hasattr(result, "__all__")

    def test_import_mod_module_not_found(self):
        """Test error handling when module doesn't exist."""
        with pytest.raises(ImportError, match="not found"):
            import_mod("NonExistentComponent", "nonexistent_module", "lfx.components.helpers")

    def test_import_mod_attribute_not_found(self):
        """Test error handling when attribute doesn't exist in module."""
        with pytest.raises(AttributeError):
            import_mod("NonExistentComponent", "calculator_core", "lfx.components.helpers")


class TestComponentDynamicImports:
    """Test dynamic import behavior in component modules."""

    def test_main_components_module_dynamic_import(self):
        """Test that main components module allows direct submodule imports."""
        # Test direct imports work
        import lfx.components.helpers
        import lfx.components.input_output

        # These should be importable modules
        assert lfx.components.helpers is not None
        assert lfx.components.input_output is not None

        # Should have the expected structure
        assert hasattr(lfx.components.helpers, "__all__")
        assert "CalculatorComponent" in lfx.components.helpers.__all__

    def test_main_components_module_dir(self):
        """Test component module structure."""
        # Test that we can import components directly
        import lfx.components.helpers
        import lfx.components.input_output

        # These modules should have the expected structure
        assert hasattr(lfx.components.helpers, "__all__")
        assert hasattr(lfx.components.input_output, "__all__")

        # Test __dir__ works on the component modules themselves
        helpers_dir = dir(lfx.components.helpers)
        assert "CalculatorComponent" in helpers_dir

    def test_main_components_module_missing_attribute(self):
        """Test error handling for non-existent component category."""
        from lfx import components

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent_category'"):
            _ = components.nonexistent_category

    def test_category_module_dynamic_import(self):
        """Test dynamic import behavior in category modules like helpers."""
        import lfx.components.helpers as helpers_components

        # Test that components are in __all__
        assert "CalculatorComponent" in helpers_components.__all__
        assert "CurrentDateComponent" in helpers_components.__all__

        # Access component - this should work via dynamic import
        calc_component = helpers_components.CalculatorComponent
        assert calc_component is not None

        # Should be cached in globals after access
        assert "CalculatorComponent" in helpers_components.__dict__
        assert helpers_components.__dict__["CalculatorComponent"] is calc_component

        # Second access should return cached version
        calc_component_2 = helpers_components.CalculatorComponent
        assert calc_component_2 is calc_component

    def test_category_module_dir(self):
        """Test __dir__ functionality for category modules."""
        import lfx.components.helpers as helpers_components

        dir_result = dir(helpers_components)
        assert "CalculatorComponent" in dir_result
        assert "CurrentDateComponent" in dir_result

    def test_category_module_missing_component(self):
        """Test error handling for non-existent component in category."""
        import lfx.components.helpers as helpers_components

        with pytest.raises(AttributeError, match="has no attribute 'NonExistentComponent'"):
            _ = helpers_components.NonExistentComponent

    def test_multiple_category_modules(self):
        """Test dynamic imports work across multiple category modules."""
        import lfx.components.helpers as helpers_components
        import lfx.components.processing as processing_components

        # Test different categories work independently
        calc_component = helpers_components.CalculatorComponent
        combine_text = processing_components.CombineTextComponent

        assert calc_component is not None
        assert combine_text is not None

        # Test they're cached in their respective modules
        assert "CalculatorComponent" in helpers_components.__dict__
        assert "CombineTextComponent" in processing_components.__dict__

    def test_backward_compatibility(self):
        """Test that existing import patterns still work."""
        # These imports should work the same as before - using components without external deps
        from lfx.components.helpers import CalculatorComponent
        from lfx.components.input_output import TextInputComponent
        from lfx.components.processing import CombineTextComponent

        assert CalculatorComponent is not None
        assert CombineTextComponent is not None
        assert TextInputComponent is not None

    def test_component_instantiation(self):
        """Test that dynamically imported components can be instantiated."""
        from lfx.components import helpers

        # Import component dynamically
        calculator_class = helpers.CalculatorComponent

        # Should be able to instantiate (even if it requires parameters)
        assert callable(calculator_class)
        assert hasattr(calculator_class, "__init__")

    def test_import_error_handling(self):
        """Test error handling when import fails."""
        import lfx.components.helpers as helpers_components

        # Patch the import_mod function directly
        with patch("lfx.components.helpers.import_mod") as mock_import_mod:
            # Mock import_mod to raise ImportError
            mock_import_mod.side_effect = ImportError("Module not found")

            # Clear any cached attribute
            if "CalculatorComponent" in helpers_components.__dict__:
                del helpers_components.__dict__["CalculatorComponent"]

            with pytest.raises(AttributeError, match="Could not import"):
                _ = helpers_components.CalculatorComponent

    def test_consistency_check(self):
        """Test that __all__ and _dynamic_imports are consistent."""
        import lfx.components.helpers as helpers_components

        # All items in __all__ should have corresponding entries in _dynamic_imports
        for component_name in helpers_components.__all__:
            assert component_name in helpers_components._dynamic_imports

        # All keys in _dynamic_imports should be in __all__
        for component_name in helpers_components._dynamic_imports:
            assert component_name in helpers_components.__all__

    def test_type_checking_imports(self):
        """Test that TYPE_CHECKING imports work correctly with dynamic loading."""
        # This test ensures that imports in TYPE_CHECKING blocks
        # work correctly with the dynamic import system
        import lfx.components.processing as processing_components

        # Components should be available for dynamic loading
        assert "CombineTextComponent" in processing_components.__all__
        assert "CombineTextComponent" in processing_components._dynamic_imports

        # Accessing should trigger dynamic import and caching
        component = processing_components.CombineTextComponent
        assert component is not None
        assert "CombineTextComponent" in processing_components.__dict__


class TestPerformanceCharacteristics:
    """Test performance characteristics of dynamic imports."""

    def test_lazy_loading_performance(self):
        """Test that components can be accessed and cached properly."""
        from lfx.components import processing

        # Test that we can access a component
        combine_text = processing.CombineTextComponent
        assert combine_text is not None

        # After access, it should be cached in the module's globals
        assert "CombineTextComponent" in processing.__dict__

        # Subsequent access should return the same cached object
        combine_text_2 = processing.CombineTextComponent
        assert combine_text_2 is combine_text

    def test_caching_behavior(self):
        """Test that components are cached after first access."""
        from lfx.components import helpers

        # First access
        calc_component_1 = helpers.CalculatorComponent

        # Second access should return the exact same object (cached)
        calc_component_2 = helpers.CalculatorComponent

        assert calc_component_1 is calc_component_2

    def test_memory_usage_multiple_accesses(self):
        """Test memory behavior with multiple component accesses."""
        from lfx.components import processing

        # Access multiple components
        components = []
        component_names = ["CombineTextComponent", "CreateDataComponent", "JSONCleaner", "RegexExtractorComponent"]

        for name in component_names:
            component = getattr(processing, name)
            components.append(component)
            # Each should be cached
            assert name in processing.__dict__

        # All should be different classes
        assert len(set(components)) == len(components)


class TestSpecialCases:
    """Test special cases and edge conditions."""

    def test_empty_init_files(self):
        """Test that empty __init__.py files are handled gracefully."""
        # Test accessing components from categories that might have empty __init__.py
        from lfx import components

        # These should work even if some categories have empty __init__.py files
        agents = components.agents
        assert agents is not None

    def test_platform_specific_components(self):
        """Test component handling for modules without external dependencies."""
        import lfx.components.input_output as io_components

        # Input/Output components should be available
        text_input = io_components.TextInputComponent
        assert text_input is not None

        # Components should be handled correctly
        # (This test will pass since these components have no external dependencies)
        assert "TextInputComponent" in io_components.__all__

    def test_import_structure_integrity(self):
        """Test that the import structure maintains integrity."""
        from lfx import components

        # Test that we can access nested components through the hierarchy
        calc_component = components.helpers.CalculatorComponent
        text_input = components.input_output.TextInputComponent

        assert calc_component is not None
        assert text_input is not None

        # Test that both main module and submodules are properly cached
        assert "helpers" in components.__dict__
        assert "input_output" in components.__dict__


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
