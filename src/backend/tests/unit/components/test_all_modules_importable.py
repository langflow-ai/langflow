"""Test to ensure all component modules are importable after dynamic import refactor.

This test validates that every component module can be imported successfully
and that all components listed in __all__ can be accessed.
"""

import importlib

import pytest
from langflow import components


class TestAllModulesImportable:
    """Test that all component modules are importable."""

    def test_all_component_categories_importable(self):
        """Test that all component categories in __all__ can be imported."""
        failed_imports = []

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)
                assert category_module is not None, f"Category {category_name} is None"

                # Verify it's actually a module
                assert hasattr(category_module, "__name__"), f"Category {category_name} is not a module"

            except Exception as e:  # noqa: BLE001
                failed_imports.append(f"{category_name}: {e!s}")

        if failed_imports:
            pytest.fail(f"Failed to import categories: {failed_imports}")

    def test_all_components_in_categories_importable(self):
        """Test that all components in each category's __all__ can be imported."""
        failed_imports = []
        successful_imports = 0

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)

                if hasattr(category_module, "__all__"):
                    for component_name in category_module.__all__:
                        try:
                            component = getattr(category_module, component_name)
                            assert component is not None, f"Component {component_name} is None"
                            assert callable(component), f"Component {component_name} is not callable"
                            successful_imports += 1

                        except Exception as e:  # noqa: BLE001
                            failed_imports.append(f"{category_name}.{component_name}: {e!s}")
                else:
                    # Category doesn't have __all__, skip
                    continue

            except Exception as e:  # noqa: BLE001
                failed_imports.append(f"Category {category_name}: {e!s}")

        print(f"Successfully imported {successful_imports} components")  # noqa: T201

        if failed_imports:
            print(f"Failed imports ({len(failed_imports)}):")  # noqa: T201
            for failure in failed_imports[:10]:  # Show first 10 failures
                print(f"  - {failure}")  # noqa: T201
            if len(failed_imports) > 10:
                print(f"  ... and {len(failed_imports) - 10} more")  # noqa: T201

            pytest.fail(f"Failed to import {len(failed_imports)} components")

    def test_dynamic_imports_mapping_complete(self):
        """Test that _dynamic_imports mapping is complete for all categories."""
        failed_mappings = []

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)

                if hasattr(category_module, "__all__") and hasattr(category_module, "_dynamic_imports"):
                    category_all = set(category_module.__all__)
                    dynamic_imports_keys = set(category_module._dynamic_imports.keys())

                    # Check that all items in __all__ have corresponding _dynamic_imports entries
                    missing_in_dynamic = category_all - dynamic_imports_keys
                    if missing_in_dynamic:
                        failed_mappings.append(f"{category_name}: Missing in _dynamic_imports: {missing_in_dynamic}")

                    # Check that all _dynamic_imports keys are in __all__
                    missing_in_all = dynamic_imports_keys - category_all
                    if missing_in_all:
                        failed_mappings.append(f"{category_name}: Missing in __all__: {missing_in_all}")

            except Exception as e:  # noqa: BLE001
                failed_mappings.append(f"{category_name}: Error checking mappings: {e!s}")

        if failed_mappings:
            pytest.fail(f"Inconsistent mappings: {failed_mappings}")

    def test_backward_compatibility_imports(self):
        """Test that traditional import patterns still work."""
        # Test some key imports that should always work
        traditional_imports = [
            ("langflow.components.openai", "OpenAIModelComponent"),
            ("langflow.components.anthropic", "AnthropicModelComponent"),
            ("langflow.components.data", "APIRequestComponent"),
            ("langflow.components.agents", "AgentComponent"),
            ("langflow.components.helpers", "CalculatorComponent"),
        ]

        failed_imports = []

        for module_name, component_name in traditional_imports:
            try:
                module = importlib.import_module(module_name)
                component = getattr(module, component_name)
                assert component is not None
                assert callable(component)

            except Exception as e:  # noqa: BLE001
                failed_imports.append(f"{module_name}.{component_name}: {e!s}")

        if failed_imports:
            pytest.fail(f"Traditional imports failed: {failed_imports}")

    def test_component_modules_have_required_attributes(self):
        """Test that component modules have required attributes for dynamic loading."""
        failed_modules = []

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)

                # Check for required attributes
                required_attrs = ["__all__"]

                failed_modules.extend(
                    f"{category_name}: Missing required attribute {attr}"
                    for attr in required_attrs
                    if not hasattr(category_module, attr)
                )

                # Check that if it has dynamic imports, it has the pattern
                if hasattr(category_module, "_dynamic_imports"):
                    if not hasattr(category_module, "__getattr__"):
                        failed_modules.append(f"{category_name}: Has _dynamic_imports but no __getattr__")
                    if not hasattr(category_module, "__dir__"):
                        failed_modules.append(f"{category_name}: Has _dynamic_imports but no __dir__")

            except Exception as e:  # noqa: BLE001
                failed_modules.append(f"{category_name}: Error checking attributes: {e!s}")

        if failed_modules:
            pytest.fail(f"Module attribute issues: {failed_modules}")

    def test_no_circular_imports(self):
        """Test that there are no circular import issues."""
        # Test importing in different orders to catch circular imports
        import_orders = [
            ["agents", "data", "openai"],
            ["openai", "agents", "data"],
            ["data", "openai", "agents"],
        ]

        for order in import_orders:
            try:
                for category_name in order:
                    category_module = getattr(components, category_name)
                    # Access a component to trigger dynamic import
                    if hasattr(category_module, "__all__") and category_module.__all__:
                        first_component_name = category_module.__all__[0]
                        getattr(category_module, first_component_name)

            except Exception as e:  # noqa: BLE001
                pytest.fail(f"Circular import issue with order {order}: {e!s}")

    def test_component_access_caching(self):
        """Test that component access caching works correctly."""
        # Access the same component multiple times and ensure caching works
        test_cases = [
            ("openai", "OpenAIModelComponent"),
            ("data", "APIRequestComponent"),
            ("helpers", "CalculatorComponent"),
        ]

        for category_name, component_name in test_cases:
            category_module = getattr(components, category_name)

            # First access
            component1 = getattr(category_module, component_name)

            # Component should now be cached in module globals
            assert component_name in category_module.__dict__

            # Second access should return the same object
            component2 = getattr(category_module, component_name)
            assert component1 is component2, f"Caching failed for {category_name}.{component_name}"

    def test_error_handling_for_missing_components(self):
        """Test that appropriate errors are raised for missing components."""
        test_cases = [
            ("openai", "NonExistentComponent"),
            ("data", "AnotherNonExistentComponent"),
        ]

        for category_name, component_name in test_cases:
            category_module = getattr(components, category_name)

            with pytest.raises(AttributeError, match=f"has no attribute '{component_name}'"):
                getattr(category_module, component_name)

    def test_dir_functionality(self):
        """Test that __dir__ functionality works for all modules."""
        # Test main components module
        main_dir = dir(components)
        assert "openai" in main_dir
        assert "data" in main_dir
        assert "agents" in main_dir

        # Test category modules
        for category_name in ["openai", "data", "helpers"]:
            category_module = getattr(components, category_name)
            category_dir = dir(category_module)

            # Should include all components from __all__
            if hasattr(category_module, "__all__"):
                for component_name in category_module.__all__:
                    assert component_name in category_dir, f"{component_name} missing from dir({category_name})"

    def test_module_metadata_preservation(self):
        """Test that module metadata is preserved after dynamic loading."""
        test_components = [
            ("openai", "OpenAIModelComponent"),
            ("anthropic", "AnthropicModelComponent"),
            ("data", "APIRequestComponent"),
        ]

        for category_name, component_name in test_components:
            category_module = getattr(components, category_name)
            component = getattr(category_module, component_name)

            # Check that component has expected metadata
            assert hasattr(component, "__name__")
            assert hasattr(component, "__module__")
            assert component.__name__ == component_name
            assert category_name in component.__module__


class TestSpecificModulePatterns:
    """Test specific module patterns and edge cases."""

    def test_empty_init_modules(self):
        """Test modules that might have empty __init__.py files."""
        # These modules might have empty __init__.py files in the original structure
        potentially_empty_modules = [
            "chains",
            "output_parsers",
            "textsplitters",
            "toolkits",
            "link_extractors",
            "documentloaders",
        ]

        for module_name in potentially_empty_modules:
            if module_name in components.__all__:
                try:
                    module = getattr(components, module_name)
                    # Should be able to import even if empty
                    assert module is not None
                except Exception as e:  # noqa: BLE001
                    pytest.fail(f"Failed to import potentially empty module {module_name}: {e}")

    def test_platform_specific_imports(self):
        """Test platform-specific imports like NVIDIA Windows components."""
        # Test NVIDIA module which has platform-specific logic
        nvidia_module = components.nvidia
        assert nvidia_module is not None

        # Should have basic components regardless of platform
        assert "NVIDIAModelComponent" in nvidia_module.__all__

        # Should be able to access components
        nvidia_model = nvidia_module.NVIDIAModelComponent
        assert nvidia_model is not None

    def test_large_modules_import_efficiently(self):
        """Test that large modules with many components import efficiently."""
        import time

        # Test large modules
        large_modules = ["vectorstores", "processing", "langchain_utilities"]

        for module_name in large_modules:
            if module_name in components.__all__:
                start_time = time.time()
                module = getattr(components, module_name)
                import_time = time.time() - start_time

                # Initial import should be fast (just loading __init__.py)
                assert import_time < 0.5, f"Module {module_name} took too long to import: {import_time}s"

                # Should have components available
                assert hasattr(module, "__all__")
                assert len(module.__all__) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
