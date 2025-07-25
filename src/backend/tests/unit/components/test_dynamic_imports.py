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
from langflow.components._importing import import_mod


class TestImportUtils:
    """Test the import_mod utility function."""

    def test_import_mod_with_module_name(self):
        """Test importing specific attribute from a module."""
        # Test importing a specific class from a module
        result = import_mod("OpenAIModelComponent", "openai_chat_model", "langflow.components.openai")
        assert result is not None
        assert hasattr(result, "__name__")
        assert "OpenAI" in result.__name__

    def test_import_mod_without_module_name(self):
        """Test importing entire module when module_name is None."""
        result = import_mod("agents", "__module__", "langflow.components")
        assert result is not None
        # Should return the agents module
        assert hasattr(result, "__all__")

    def test_import_mod_module_not_found(self):
        """Test error handling when module doesn't exist."""
        with pytest.raises(ImportError, match="not found"):
            import_mod("NonExistentComponent", "nonexistent_module", "langflow.components.openai")

    def test_import_mod_attribute_not_found(self):
        """Test error handling when attribute doesn't exist in module."""
        with pytest.raises(AttributeError):
            import_mod("NonExistentComponent", "openai_chat_model", "langflow.components.openai")


class TestComponentDynamicImports:
    """Test dynamic import behavior in component modules."""

    def test_main_components_module_dynamic_import(self):
        """Test that main components module imports submodules dynamically."""
        # Import the main components module
        from langflow import components

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
        from langflow import components

        dir_result = dir(components)
        # Should include all component categories
        assert "agents" in dir_result
        assert "data" in dir_result
        assert "openai" in dir_result
        assert "vectorstores" in dir_result

    def test_main_components_module_missing_attribute(self):
        """Test error handling for non-existent component category."""
        from langflow import components

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent_category'"):
            _ = components.nonexistent_category

    def test_category_module_dynamic_import(self):
        """Test dynamic import behavior in category modules like openai."""
        import langflow.components.openai as openai_components

        # Test that components are in __all__
        assert "OpenAIModelComponent" in openai_components.__all__
        assert "OpenAIEmbeddingsComponent" in openai_components.__all__

        # Access component - this should work via dynamic import
        openai_model = openai_components.OpenAIModelComponent
        assert openai_model is not None

        # Should be cached in globals after access
        assert "OpenAIModelComponent" in openai_components.__dict__
        assert openai_components.__dict__["OpenAIModelComponent"] is openai_model

        # Second access should return cached version
        openai_model_2 = openai_components.OpenAIModelComponent
        assert openai_model_2 is openai_model

    def test_category_module_dir(self):
        """Test __dir__ functionality for category modules."""
        import langflow.components.openai as openai_components

        dir_result = dir(openai_components)
        assert "OpenAIModelComponent" in dir_result
        assert "OpenAIEmbeddingsComponent" in dir_result

    def test_category_module_missing_component(self):
        """Test error handling for non-existent component in category."""
        import langflow.components.openai as openai_components

        with pytest.raises(AttributeError, match="has no attribute 'NonExistentComponent'"):
            _ = openai_components.NonExistentComponent

    def test_multiple_category_modules(self):
        """Test dynamic imports work across multiple category modules."""
        import langflow.components.anthropic as anthropic_components
        import langflow.components.data as data_components

        # Test different categories work independently
        anthropic_model = anthropic_components.AnthropicModelComponent
        api_request = data_components.APIRequestComponent

        assert anthropic_model is not None
        assert api_request is not None

        # Test they're cached in their respective modules
        assert "AnthropicModelComponent" in anthropic_components.__dict__
        assert "APIRequestComponent" in data_components.__dict__

    def test_backward_compatibility(self):
        """Test that existing import patterns still work."""
        # These imports should work the same as before
        from langflow.components.agents import AgentComponent
        from langflow.components.data import APIRequestComponent
        from langflow.components.openai import OpenAIModelComponent

        assert OpenAIModelComponent is not None
        assert APIRequestComponent is not None
        assert AgentComponent is not None

    def test_component_instantiation(self):
        """Test that dynamically imported components can be instantiated."""
        from langflow.components import helpers

        # Import component dynamically
        calculator_class = helpers.CalculatorComponent

        # Should be able to instantiate (even if it requires parameters)
        assert callable(calculator_class)
        assert hasattr(calculator_class, "__init__")

    @patch("langflow.components._import_utils.import_module")
    def test_import_error_handling(self, mock_import_module):
        """Test error handling when import fails."""
        # Mock import_module to raise ImportError
        mock_import_module.side_effect = ImportError("Module not found")

        # Import a fresh module to test error handling
        import langflow.components.notdiamond as notdiamond_components

        with pytest.raises(AttributeError, match="Could not import"):
            _ = notdiamond_components.NotDiamondComponent

    def test_consistency_check(self):
        """Test that __all__ and _dynamic_imports are consistent."""
        import langflow.components.openai as openai_components

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
        import langflow.components.searchapi as searchapi_components

        # Components should be available for dynamic loading
        assert "SearchComponent" in searchapi_components.__all__
        assert "SearchComponent" in searchapi_components._dynamic_imports

        # Accessing should trigger dynamic import and caching
        component = searchapi_components.SearchComponent
        assert component is not None
        assert "SearchComponent" in searchapi_components.__dict__


class TestPerformanceCharacteristics:
    """Test performance characteristics of dynamic imports."""

    def test_lazy_loading_performance(self):
        """Test that components can be accessed and cached properly."""
        from langflow.components import vectorstores

        # Test that we can access a component
        chroma = vectorstores.ChromaVectorStoreComponent
        assert chroma is not None

        # After access, it should be cached in the module's globals
        assert "ChromaVectorStoreComponent" in vectorstores.__dict__

        # Subsequent access should return the same cached object
        chroma_2 = vectorstores.ChromaVectorStoreComponent
        assert chroma_2 is chroma

    def test_caching_behavior(self):
        """Test that components are cached after first access."""
        from langflow.components import models

        # First access
        embedding_model_1 = models.EmbeddingModelComponent

        # Second access should return the exact same object (cached)
        embedding_model_2 = models.EmbeddingModelComponent

        assert embedding_model_1 is embedding_model_2

    def test_memory_usage_multiple_accesses(self):
        """Test memory behavior with multiple component accesses."""
        from langflow.components import processing

        # Access multiple components
        components = []
        component_names = ["CombineTextComponent", "SplitTextComponent", "JSONCleaner", "RegexExtractorComponent"]

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
        from langflow import components

        # These should work even if some categories have empty __init__.py files
        agents = components.agents
        assert agents is not None

    def test_platform_specific_components(self):
        """Test platform-specific component handling (like NVIDIA Windows components)."""
        import langflow.components.nvidia as nvidia_components

        # NVIDIA components should be available
        nvidia_model = nvidia_components.NVIDIAModelComponent
        assert nvidia_model is not None

        # Platform-specific components should be handled correctly
        # (This test will pass regardless of platform since the import structure handles it)
        assert "NVIDIAModelComponent" in nvidia_components.__all__

    def test_import_structure_integrity(self):
        """Test that the import structure maintains integrity."""
        from langflow import components

        # Test that we can access nested components through the hierarchy
        openai_model = components.openai.OpenAIModelComponent
        data_api = components.data.APIRequestComponent

        assert openai_model is not None
        assert data_api is not None

        # Test that both main module and submodules are properly cached
        assert "openai" in components.__dict__
        assert "data" in components.__dict__


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
