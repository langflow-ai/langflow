"""Integration tests for the component dynamic import system.

These tests intentionally use core components only. Provider/bundle component
compatibility belongs in the owning bundle's test suite so the core Langflow
test suite keeps collecting when optional bundles are not installed.
"""

import sys
import threading
import time

import pytest
from langflow.components.data import APIRequestComponent
from langflow.components.models_and_agents import AgentComponent, LanguageModelComponent


class TestDynamicImportIntegration:
    """Integration tests for the dynamic import system."""

    def test_component_discovery_still_works(self):
        from langflow import components

        data_module = components.data
        assert hasattr(data_module, "APIRequestComponent")

        helpers_module = components.helpers
        assert hasattr(helpers_module, "CalculatorComponent")

        models_module = components.models_and_agents
        assert hasattr(models_module, "LanguageModelComponent")

    def test_existing_import_patterns_work(self):
        import langflow.components.data as data_comp
        import langflow.components.helpers as helpers_comp

        assert APIRequestComponent is not None
        assert AgentComponent is not None
        assert LanguageModelComponent is not None
        assert data_comp.APIRequestComponent is not None
        assert helpers_comp.CalculatorComponent is not None

    def test_component_instantiation_works(self):
        from langflow.components.helpers import CalculatorComponent

        assert CalculatorComponent is not None
        assert callable(CalculatorComponent)

    def test_template_creation_compatibility(self):
        for component_class in (APIRequestComponent, LanguageModelComponent):
            assert hasattr(component_class, "__name__")
            assert hasattr(component_class, "__module__")
            assert hasattr(component_class, "display_name")
            assert isinstance(component_class.display_name, str)
            assert component_class.display_name
            assert hasattr(component_class, "description")
            assert isinstance(component_class.description, str)
            assert component_class.description
            assert hasattr(component_class, "icon")
            assert isinstance(component_class.icon, str)
            assert component_class.icon
            assert hasattr(component_class, "inputs")
            assert isinstance(component_class.inputs, list)
            assert len(component_class.inputs) > 0
            for input_field in component_class.inputs:
                assert hasattr(input_field, "name"), f"Input {input_field} missing 'name' attribute"
                assert hasattr(input_field, "display_name"), f"Input {input_field} missing 'display_name' attribute"

    def test_multiple_import_styles_same_result(self):
        from langflow import components
        from langflow.components.data import APIRequestComponent as DirectImport

        dynamic_import = components.data.APIRequestComponent

        import langflow.components.data as data_module

        module_import = data_module.APIRequestComponent

        assert DirectImport is dynamic_import
        assert dynamic_import is module_import
        assert DirectImport is module_import

    def test_startup_performance_improvement(self):
        modules_to_clean = [
            "langflow.components.processing",
            "langflow.components.tools",
            "langflow.components.langchain_utilities",
        ]

        for module_name in modules_to_clean:
            if module_name in sys.modules:
                del sys.modules[module_name]

        start_time = time.time()
        from langflow.components import processing

        import_time = time.time() - start_time

        assert import_time < 0.1

        start_time = time.time()
        parser_component = processing.ParserComponent
        access_time = time.time() - start_time

        assert parser_component is not None
        assert access_time < 2.0

    def test_memory_usage_efficiency(self):
        from langflow.components import processing

        initial_component_count = len([k for k in processing.__dict__ if k.endswith("Component")])

        combine_text = processing.CombineTextComponent
        assert combine_text is not None

        after_one_access = len([k for k in processing.__dict__ if k.endswith("Component")])
        assert after_one_access >= initial_component_count

        split_text = processing.SplitTextComponent
        assert split_text is not None

        after_two_access = len([k for k in processing.__dict__ if k.endswith("Component")])
        assert after_two_access >= after_one_access

    def test_error_handling_in_realistic_scenarios(self):
        from langflow import components

        with pytest.raises(AttributeError):
            _ = components.nonexistent_category

        with pytest.raises(AttributeError):
            _ = components.data.NonExistentComponent

    def test_ide_autocomplete_support(self):
        import langflow.components.data as data_components
        from langflow import components

        main_dir = dir(components)
        assert "data" in main_dir
        assert "helpers" in main_dir
        assert "models_and_agents" in main_dir

        data_dir = dir(data_components)
        assert "APIRequestComponent" in data_dir

    def test_concurrent_access(self):
        from langflow.components import helpers

        results = []
        errors = []

        def access_component():
            try:
                component = helpers.CalculatorComponent
                results.append(component)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_component)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 5

        first_result = results[0]
        for result in results[1:]:
            assert result is first_result

    def test_circular_import_prevention(self):
        from langflow import components
        from langflow.components import data

        component1 = components.data.APIRequestComponent
        component2 = data.APIRequestComponent
        component3 = APIRequestComponent

        assert component1 is component2 is component3

    def test_large_scale_component_access(self):
        from langflow.components import data

        component_names = [
            "APIRequestComponent",
            "DirectoryComponent",
            "FileComponent",
            "URLComponent",
        ]

        components_accessed = [getattr(data, name) for name in component_names if hasattr(data, name)]

        assert len(components_accessed) == len(component_names)
        assert len(set(components_accessed)) == len(components_accessed)

    def test_component_metadata_preservation(self):
        assert hasattr(APIRequestComponent, "__name__")
        assert hasattr(APIRequestComponent, "__module__")
        assert hasattr(APIRequestComponent, "__doc__")
        assert "data" in APIRequestComponent.__module__

    def test_backwards_compatibility_comprehensive(self):
        from langflow.components.data import APIRequestComponent as DirectAPIRequest

        assert AgentComponent is not None
        assert DirectAPIRequest is not None

        import langflow.components as comp
        import langflow.components.data as data_mod
        import langflow.components.helpers as helpers_mod

        nested_component = comp.data.APIRequestComponent
        direct_component = data_mod.APIRequestComponent

        assert data_mod.APIRequestComponent is not None
        assert helpers_mod.CalculatorComponent is not None
        assert nested_component is direct_component
