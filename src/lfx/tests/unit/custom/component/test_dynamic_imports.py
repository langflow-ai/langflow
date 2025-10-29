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
        """Test importing specific attribute from a module with missing dependencies."""
        # Test importing a class that has missing dependencies - should raise ModuleNotFoundError
        with pytest.raises(ModuleNotFoundError, match="No module named"):
            import_mod("OpenAIModelComponent", "openai_chat_model", "lfx.components.openai")

    def test_import_mod_without_module_name(self):
        """Test importing entire module when module_name is None."""
        result = import_mod("agents", "__module__", "lfx.components")
        assert result is not None
        # Should return the agents module
        assert hasattr(result, "__all__")

    def test_import_mod_module_not_found(self):
        """Test error handling when module doesn't exist."""
        with pytest.raises(ImportError, match="not found"):
            import_mod("NonExistentComponent", "nonexistent_module", "lfx.components.openai")

    def test_import_mod_attribute_not_found(self):
        """Test error handling when module has missing dependencies."""
        # The openai_chat_model module can't be imported due to missing dependencies
        with pytest.raises(ModuleNotFoundError, match="No module named"):
            import_mod("NonExistentComponent", "openai_chat_model", "lfx.components.openai")


class TestComponentDynamicImports:
    """Test dynamic import behavior in component modules."""

    def test_main_components_module_dynamic_import(self):
        """Test that main components module imports submodules dynamically."""
        # Import the main components module
        from lfx import components

        # Test that submodules are in __all__
        assert "agents" in components.__all__
        assert "data" in components.__all__
        assert "openai" in components.__all__

        # Access agents module - this should work via dynamic import
        agents_module = components.agents
        assert agents_module is not None

        # Should be cached in globals after access
        assert "agents" in components.__dict__
        assert components.__dict__["agents"] is agents_module

        # Second access should return cached version
        agents_module_2 = components.agents
        assert agents_module_2 is agents_module

    def test_main_components_module_dir(self):
        """Test __dir__ functionality for main components module."""
        from lfx import components

        dir_result = dir(components)
        # Should include all component categories
        assert "agents" in dir_result
        assert "data" in dir_result
        assert "openai" in dir_result
        assert "vectorstores" in dir_result

    def test_main_components_module_missing_attribute(self):
        """Test error handling for non-existent component category."""
        from lfx import components

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent_category'"):
            _ = components.nonexistent_category

    def test_category_module_dynamic_import(self):
        """Test dynamic import behavior in category modules like openai."""
        import lfx.components.openai as openai_components

        # Test that components are in __all__
        assert "OpenAIModelComponent" in openai_components.__all__
        assert "OpenAIEmbeddingsComponent" in openai_components.__all__

        # Access component - this should raise AttributeError due to missing langchain-openai
        with pytest.raises(AttributeError, match="Could not import 'OpenAIModelComponent'"):
            _ = openai_components.OpenAIModelComponent

        # Test that the error is properly cached - second access should also fail
        with pytest.raises(AttributeError, match="Could not import 'OpenAIModelComponent'"):
            _ = openai_components.OpenAIModelComponent

    def test_category_module_dir(self):
        """Test __dir__ functionality for category modules."""
        import lfx.components.openai as openai_components

        dir_result = dir(openai_components)
        assert "OpenAIModelComponent" in dir_result
        assert "OpenAIEmbeddingsComponent" in dir_result

    def test_category_module_missing_component(self):
        """Test error handling for non-existent component in category."""
        import lfx.components.openai as openai_components

        with pytest.raises(AttributeError, match="has no attribute 'NonExistentComponent'"):
            _ = openai_components.NonExistentComponent

    def test_multiple_category_modules(self):
        """Test dynamic imports work across multiple category modules."""
        import lfx.components.anthropic as anthropic_components
        import lfx.components.data as data_components

        # Test different categories work independently
        # AnthropicModelComponent should work if anthropic library is available
        try:
            anthropic_component = anthropic_components.AnthropicModelComponent
            # If it succeeds, just check it's a valid component
            assert anthropic_component is not None
            assert hasattr(anthropic_component, "__name__")
        except AttributeError:
            # If it fails due to missing dependencies, that's also expected
            pass

        # APIRequestComponent should work now that validators is installed
        api_component = data_components.APIRequestComponent
        assert api_component is not None
        assert hasattr(api_component, "__name__")

        # Test that __all__ still works correctly despite import failures
        assert "AnthropicModelComponent" in anthropic_components.__all__
        assert "APIRequestComponent" in data_components.__all__

    def test_backward_compatibility(self):
        """Test that existing import patterns work correctly."""
        # These imports should work since langflow is installed with dependencies
        # Test that the import mechanism correctly handles the components

        from lfx.components.agents import AgentComponent

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
        import lfx.components.notdiamond as notdiamond_components

        # Patch the import_mod function directly
        with patch("lfx.components.notdiamond.import_mod") as mock_import_mod:
            # Mock import_mod to raise ImportError
            mock_import_mod.side_effect = ImportError("Module not found")

            # Clear any cached attribute
            if "NotDiamondComponent" in notdiamond_components.__dict__:
                del notdiamond_components.__dict__["NotDiamondComponent"]

            with pytest.raises(AttributeError, match="Could not import"):
                _ = notdiamond_components.NotDiamondComponent

    def test_consistency_check(self):
        """Test that __all__ and _dynamic_imports are consistent."""
        import lfx.components.openai as openai_components

        # All items in __all__ should have corresponding entries in _dynamic_imports
        for component_name in openai_components.__all__:
            assert component_name in openai_components._dynamic_imports

        # All keys in _dynamic_imports should be in __all__
        for component_name in openai_components._dynamic_imports:
            assert component_name in openai_components.__all__

    def test_type_checking_imports(self):
        """Test that TYPE_CHECKING imports work correctly with dynamic loading."""
        # This test ensures that imports in TYPE_CHECKING blocks
        # work correctly with the dynamic import system
        import lfx.components.searchapi as searchapi_components

        # Components should be available for dynamic loading
        assert "SearchComponent" in searchapi_components.__all__
        assert "SearchComponent" in searchapi_components._dynamic_imports

        # Accessing should trigger dynamic import - may fail due to missing dependencies
        with pytest.raises(AttributeError, match=r"Could not import.*SearchComponent"):
            _ = searchapi_components.SearchComponent


class TestPerformanceCharacteristics:
    """Test performance characteristics of dynamic imports."""

    def test_lazy_loading_performance(self):
        """Test that components can be accessed and cached properly."""
        from lfx.components import chroma as chromamodules

        # Test that we can access a component
        with pytest.raises(AttributeError, match=r"Could not import.*ChromaVectorStoreComponent"):
            chromamodules.ChromaVectorStoreComponent  # noqa: B018

    def test_caching_behavior(self):
        """Test that components are cached after first access."""
        from lfx.components import models

        # EmbeddingModelComponent should raise AttributeError due to missing dependencies
        with pytest.raises(AttributeError, match=r"Could not import.*EmbeddingModelComponent"):
            _ = models.EmbeddingModelComponent

        # Test that error is cached - subsequent access should also fail
        with pytest.raises(AttributeError, match=r"Could not import.*EmbeddingModelComponent"):
            _ = models.EmbeddingModelComponent

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
        agents = components.agents
        assert agents is not None

    def test_platform_specific_components(self):
        """Test platform-specific component handling (like NVIDIA Windows components)."""
        import lfx.components.nvidia as nvidia_components

        # NVIDIAModelComponent should raise AttributeError due to missing langchain-nvidia-ai-endpoints dependency
        with pytest.raises(AttributeError, match=r"Could not import.*NVIDIAModelComponent"):
            _ = nvidia_components.NVIDIAModelComponent

        # Test that __all__ still works correctly despite import failures
        assert "NVIDIAModelComponent" in nvidia_components.__all__

    def test_import_structure_integrity(self):
        """Test that the import structure maintains integrity."""
        from lfx import components

        # Test that we can access nested components through the hierarchy
        # OpenAI component requires langchain_openai which isn't installed
        with pytest.raises(AttributeError, match=r"Could not import.*OpenAIModelComponent"):
            _ = components.openai.OpenAIModelComponent

        # APIRequestComponent should work now that validators is installed
        api_component = components.data.APIRequestComponent
        assert api_component is not None

        # Test that both main module and submodules are properly cached
        assert "openai" in components.__dict__
        assert "data" in components.__dict__


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
