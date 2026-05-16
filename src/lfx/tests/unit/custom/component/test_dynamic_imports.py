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
        """Test importing a specific attribute from an in-tree module."""
        # CombineTextComponent lives at lfx.components.processing.combine_text
        # and has no third-party deps -- imports cleanly.
        result = import_mod("CombineTextComponent", "combine_text", "lfx.components.processing")
        assert result is not None
        assert "Component" in result.__name__

    def test_import_mod_without_module_name(self):
        """Test importing entire module when module_name is None."""
        result = import_mod("models_and_agents", "__module__", "lfx.components")
        assert result is not None
        # Should return the models_and_agents module
        assert hasattr(result, "__all__")

    def test_import_mod_module_not_found(self):
        """Test error handling when module doesn't exist."""
        with pytest.raises(ImportError, match="not found"):
            import_mod("NonExistentComponent", "nonexistent_module", "lfx.components.processing")

    def test_import_mod_attribute_not_found(self):
        """Test error handling when the module imports but the attribute is missing."""
        with pytest.raises(AttributeError):
            import_mod("NonExistentComponent", "combine_text", "lfx.components.processing")


class TestComponentDynamicImports:
    """Test dynamic import behavior in component modules."""

    def test_main_components_module_dynamic_import(self):
        """Test that main components module imports submodules dynamically."""
        # Import the main components module
        from lfx import components

        # Test that in-tree submodules are in __all__.  Bundle-extracted
        # categories (openai, anthropic, etc.) ship as standalone
        # ``lfx-<bundle>`` distributions and surface through
        # ``dir(components)`` via the entry-point scan, not through
        # ``__all__``.
        assert "models_and_agents" in components.__all__
        assert "data" in components.__all__
        assert "helpers" in components.__all__

        # Access models_and_agents module - this should work via dynamic import
        models_and_agents_module = components.models_and_agents
        assert models_and_agents_module is not None

        # Should be cached in globals after access
        assert "models_and_agents" in components.__dict__
        assert components.__dict__["models_and_agents"] is models_and_agents_module

        # Second access should return cached version
        models_and_agents_module_2 = components.models_and_agents
        assert models_and_agents_module_2 is models_and_agents_module

    def test_main_components_module_dir(self):
        """Test __dir__ functionality for main components module."""
        from lfx import components

        dir_result = dir(components)
        # Should include all in-tree component categories
        assert "models_and_agents" in dir_result
        assert "data" in dir_result
        assert "helpers" in dir_result
        assert "vectorstores" in dir_result

    def test_main_components_module_missing_attribute(self):
        """Test error handling for non-existent component category."""
        from lfx import components

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent_category'"):
            _ = components.nonexistent_category

    def test_category_module_dynamic_import(self):
        """Test dynamic import behavior in an in-tree category module."""
        import lfx.components.helpers as helpers_components

        assert "CalculatorComponent" in helpers_components.__all__

        component = helpers_components.CalculatorComponent
        assert component is not None
        assert hasattr(component, "__name__")

        # Second access should return the same cached object.
        assert helpers_components.CalculatorComponent is component

    def test_category_module_dir(self):
        """Test __dir__ functionality for category modules."""
        import lfx.components.helpers as helpers_components

        dir_result = dir(helpers_components)
        assert "CalculatorComponent" in dir_result

    def test_category_module_missing_component(self):
        """Test error handling for non-existent component in category."""
        import lfx.components.helpers as helpers_components

        with pytest.raises(AttributeError, match="has no attribute 'NonExistentComponent'"):
            _ = helpers_components.NonExistentComponent

    def test_multiple_category_modules(self):
        """Test dynamic imports work across multiple in-tree category modules."""
        import lfx.components.data as data_components
        import lfx.components.helpers as helpers_components

        calculator_component = helpers_components.CalculatorComponent
        assert calculator_component is not None
        assert hasattr(calculator_component, "__name__")

        api_component = data_components.APIRequestComponent
        assert api_component is not None
        assert hasattr(api_component, "__name__")

        assert "CalculatorComponent" in helpers_components.__all__
        assert "APIRequestComponent" in data_components.__all__

    def test_backward_compatibility(self):
        """Test that existing import patterns work correctly."""
        # These imports should work since langflow is installed with dependencies
        # Test that the import mechanism correctly handles the components

        from lfx.components.models_and_agents import AgentComponent

        assert AgentComponent is not None
        assert hasattr(AgentComponent, "__init__")

        # Access components through the dynamic import mechanism
        from lfx.components import data

        api_component = data.APIRequestComponent
        assert api_component is not None
        assert hasattr(api_component, "__init__")

        # Use a component that doesn't require langchain_openai
        from lfx.components import helpers

        calc_component = helpers.CalculatorComponent
        assert calc_component is not None
        assert hasattr(calc_component, "__init__")

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
        import lfx.components.processing as processing_components

        # Patch the import_mod function directly
        with patch("lfx.components.processing.import_mod") as mock_import_mod:
            # Mock import_mod to raise ImportError
            mock_import_mod.side_effect = ImportError("Module not found")

            # Clear any cached attribute
            if "CombineTextComponent" in processing_components.__dict__:
                del processing_components.__dict__["CombineTextComponent"]

            with pytest.raises(AttributeError, match="Could not import"):
                _ = processing_components.CombineTextComponent

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
        import lfx.components.helpers as helpers_components

        assert "CalculatorComponent" in helpers_components.__all__
        assert "CalculatorComponent" in helpers_components._dynamic_imports

        # CalculatorComponent has no third-party deps and should always load.
        component = helpers_components.CalculatorComponent
        assert component is not None
        assert hasattr(component, "__init__")


class TestPerformanceCharacteristics:
    """Test performance characteristics of dynamic imports."""

    def test_lazy_loading_performance(self):
        """Test that components can be accessed and cached properly."""
        from lfx.components import helpers as helpermodules

        # Caching: a component accessed twice returns the same object.
        first = helpermodules.CalculatorComponent
        second = helpermodules.CalculatorComponent
        assert first is second

    def test_memory_usage_multiple_accesses(self):
        """Test memory behavior with multiple component accesses."""
        from lfx.components import processing

        # Access components that should work (no external dependencies)
        components = []
        component_names = ["CombineTextComponent", "JSONCleaner", "RegexExtractorComponent"]

        for name in component_names:
            component = getattr(processing, name)
            components.append(component)
            # Each should be cached
            assert name in processing.__dict__

        # All should be different classes
        assert len(set(components)) == len(components)

        # Test that SplitTextComponent works since dependencies are available
        component = processing.SplitTextComponent
        assert component is not None
        assert hasattr(component, "__init__")


class TestSpecialCases:
    """Test special cases and edge conditions."""

    def test_empty_init_files(self):
        """Test that empty __init__.py files are handled gracefully."""
        # Test accessing components from categories that might have empty __init__.py
        from lfx import components

        # These should work even if some categories have empty __init__.py files
        models_and_agents = components.models_and_agents
        assert models_and_agents is not None

    def test_platform_specific_components(self):
        """Stub: see ``src/bundles/nvidia/tests/test_nvidia_component.py``.

        Platform-specific lazy-loading was tested for the NVIDIA
        Windows components pre-extraction; that bundle now ships as
        ``lfx-nvidia`` and its lazy-loading tests live with the
        bundle.  Stub kept here so downstream tooling that
        introspects the suite layout keeps working.
        """

    def test_import_structure_integrity(self):
        """Test that the import structure maintains integrity."""
        from lfx import components

        # APIRequestComponent should work now that validators is installed.
        api_component = components.data.APIRequestComponent
        assert api_component is not None

        # CalculatorComponent has no third-party deps and should always load.
        calculator_component = components.helpers.CalculatorComponent
        assert calculator_component is not None

        # Test that both main module and submodules are properly cached.
        assert "helpers" in components.__dict__
        assert "data" in components.__dict__


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
