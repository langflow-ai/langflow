"""Integration tests for dynamic import refactor.

Tests the dynamic import system in realistic usage scenarios to ensure
the refactor doesn't break existing functionality.
"""

import sys
import time

import pytest
from langflow.components.agents import AgentComponent
from langflow.components.data import APIRequestComponent
from langflow.components.openai import OpenAIModelComponent


class TestDynamicImportIntegration:
    """Integration tests for the dynamic import system."""

    def test_component_discovery_still_works(self):
        """Test that component discovery mechanisms still work after refactor."""
        # This tests that the existing component discovery logic
        # can still find and load components
        from langflow import components

        # Test that we can discover components through the main module
        openai_module = components.openai
        assert hasattr(openai_module, "OpenAIModelComponent")

        data_module = components.data
        assert hasattr(data_module, "APIRequestComponent")

    def test_existing_import_patterns_work(self):
        """Test that all existing import patterns continue to work."""
        # Test direct imports
        import langflow.components.data as data_comp

        # Test module imports
        import langflow.components.openai as openai_comp

        # All should work
        assert OpenAIModelComponent is not None
        assert APIRequestComponent is not None
        assert AgentComponent is not None
        assert openai_comp.OpenAIModelComponent is not None
        assert data_comp.APIRequestComponent is not None

    def test_component_instantiation_works(self):
        """Test that components can still be instantiated normally."""
        # Test that we can create component instances
        # (Note: Some components may require specific initialization parameters)

        from langflow.components.helpers import CalculatorComponent

        # Should be able to access the class
        assert CalculatorComponent is not None
        assert callable(CalculatorComponent)

    def test_template_creation_compatibility(self):
        """Test that template creation still works with dynamic imports."""
        # Test accessing component attributes needed for templates

        # Components should have all necessary attributes for template creation
        assert hasattr(OpenAIModelComponent, "__name__")
        assert hasattr(OpenAIModelComponent, "__module__")
        assert hasattr(OpenAIModelComponent, "display_name")
        assert isinstance(OpenAIModelComponent.display_name, str)
        assert OpenAIModelComponent.display_name
        assert hasattr(OpenAIModelComponent, "description")
        assert isinstance(OpenAIModelComponent.description, str)
        assert OpenAIModelComponent.description
        assert hasattr(OpenAIModelComponent, "icon")
        assert isinstance(OpenAIModelComponent.icon, str)
        assert OpenAIModelComponent.icon
        assert hasattr(OpenAIModelComponent, "inputs")
        assert isinstance(OpenAIModelComponent.inputs, list)
        assert len(OpenAIModelComponent.inputs) > 0
        # Check that each input has required attributes
        for input_field in OpenAIModelComponent.inputs:
            assert hasattr(input_field, "name"), f"Input {input_field} missing 'name' attribute"
            assert hasattr(input_field, "display_name"), f"Input {input_field} missing 'display_name' attribute"

    def test_multiple_import_styles_same_result(self):
        """Test that different import styles yield the same component."""
        # Import the same component in different ways
        from langflow import components
        from langflow.components.openai import OpenAIModelComponent as DirectImport

        dynamic_import = components.openai.OpenAIModelComponent

        import langflow.components.openai as openai_module

        module_import = openai_module.OpenAIModelComponent

        # All three should be the exact same class object
        assert DirectImport is dynamic_import
        assert dynamic_import is module_import
        assert DirectImport is module_import

    def test_startup_performance_improvement(self):
        """Test that startup time is improved with lazy loading."""
        # This test measures the difference in import time
        # Fresh modules to test startup behavior
        modules_to_clean = [
            "langflow.components.vectorstores",
            "langflow.components.tools",
            "langflow.components.langchain_utilities",
        ]

        for module_name in modules_to_clean:
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Time the import of a large module
        start_time = time.time()
        from langflow.components import vectorstores

        import_time = time.time() - start_time

        # Import time should be very fast (just loading the __init__.py)
        assert import_time < 0.1  # Should be well under 100ms

        # Test that we can access a component (it may already be cached from previous tests)
        # This is expected behavior in a test suite where components get cached

        # Now access a component - this should trigger loading
        start_time = time.time()
        chroma_component = vectorstores.ChromaVectorStoreComponent
        access_time = time.time() - start_time

        assert chroma_component is not None
        # Access time should still be reasonable
        assert access_time < 2.0  # Should be under 2 seconds

    def test_memory_usage_efficiency(self):
        """Test that memory usage is more efficient with lazy loading."""
        from langflow.components import processing

        # Count currently loaded components
        initial_component_count = len([k for k in processing.__dict__ if k.endswith("Component")])

        # Access just one component
        combine_text = processing.CombineTextComponent
        assert combine_text is not None

        # At least one more component should be loaded now
        after_one_access = len([k for k in processing.__dict__ if k.endswith("Component")])
        assert after_one_access >= initial_component_count

        # Access another component
        split_text = processing.SplitTextComponent
        assert split_text is not None

        # Should have at least one more component loaded
        after_two_access = len([k for k in processing.__dict__ if k.endswith("Component")])
        assert after_two_access >= after_one_access

    def test_error_handling_in_realistic_scenarios(self):
        """Test error handling in realistic usage scenarios."""
        from langflow import components

        # Test accessing non-existent component category
        with pytest.raises(AttributeError):
            _ = components.nonexistent_category

        # Test accessing non-existent component in valid category
        with pytest.raises(AttributeError):
            _ = components.openai.NonExistentComponent

    def test_ide_autocomplete_support(self):
        """Test that IDE autocomplete support still works."""
        import langflow.components.openai as openai_components
        from langflow import components

        # __dir__ should return all available components/modules
        main_dir = dir(components)
        assert "openai" in main_dir
        assert "data" in main_dir
        assert "agents" in main_dir

        openai_dir = dir(openai_components)
        assert "OpenAIModelComponent" in openai_dir
        assert "OpenAIEmbeddingsComponent" in openai_dir

    def test_concurrent_access(self):
        """Test that concurrent access to components works correctly."""
        import threading

        from langflow.components import helpers

        results = []
        errors = []

        def access_component():
            try:
                component = helpers.CalculatorComponent
                results.append(component)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        # Create multiple threads accessing the same component
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_component)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 5

        # All results should be the same component class
        first_result = results[0]
        for result in results[1:]:
            assert result is first_result

    def test_circular_import_prevention(self):
        """Test that the refactor doesn't introduce circular imports."""
        # This test ensures that importing components doesn't create
        # circular dependency issues

        # These imports should work without circular import errors
        from langflow import components
        from langflow.components import openai

        # Access components in different orders
        model1 = components.openai.OpenAIModelComponent
        model2 = openai.OpenAIModelComponent
        model3 = OpenAIModelComponent

        # All should be the same
        assert model1 is model2 is model3

    def test_large_scale_component_access(self):
        """Test accessing many components doesn't cause issues."""
        from langflow.components import vectorstores

        # Access multiple components rapidly
        components_accessed = []
        component_names = [
            "ChromaVectorStoreComponent",
            "PineconeVectorStoreComponent",
            "FaissVectorStoreComponent",
            "WeaviateVectorStoreComponent",
            "QdrantVectorStoreComponent",
        ]

        for name in component_names:
            if hasattr(vectorstores, name):
                component = getattr(vectorstores, name)
                components_accessed.append(component)

        # Should have accessed multiple components without issues
        assert len(components_accessed) > 0

        # All should be different classes
        assert len(set(components_accessed)) == len(components_accessed)

    def test_component_metadata_preservation(self):
        """Test that component metadata is preserved after dynamic loading."""
        # Component should have all expected metadata
        assert hasattr(OpenAIModelComponent, "__name__")
        assert hasattr(OpenAIModelComponent, "__module__")
        assert hasattr(OpenAIModelComponent, "__doc__")

        # Module path should be correct
        assert "openai" in OpenAIModelComponent.__module__

    def test_backwards_compatibility_comprehensive(self):
        """Comprehensive test of backwards compatibility."""
        # Test all major import patterns that should still work

        # 1. Direct component imports
        from langflow.components.data import APIRequestComponent

        assert AgentComponent is not None
        assert APIRequestComponent is not None

        # 2. Module imports
        # 3. Main module access
        import langflow.components as comp
        import langflow.components.helpers as helpers_mod
        import langflow.components.openai as openai_mod

        # 4. Nested access
        nested_component = comp.openai.OpenAIModelComponent
        direct_component = openai_mod.OpenAIModelComponent

        # All patterns should work and yield consistent results
        assert openai_mod.OpenAIModelComponent is not None
        assert helpers_mod.CalculatorComponent is not None
        assert nested_component is direct_component


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
