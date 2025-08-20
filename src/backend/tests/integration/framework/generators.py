"""Test generators for automatic test creation."""

import inspect
from pathlib import Path
from typing import Any

from langflow.custom import Component


class ComponentTestGenerator:
    """Generates basic integration tests for components automatically."""

    def __init__(self):
        self.test_templates = {
            "basic": self._generate_basic_test,
            "contract": self._generate_contract_test,
            "error_handling": self._generate_error_test,
            "performance": self._generate_performance_test,
        }

    def generate_test_class(
        self, component_class: type[Component], test_types: list[str] | None = None, output_file: str | None = None
    ) -> str:
        """Generate a complete test class for a component.

        Args:
            component_class: Component class to generate tests for
            test_types: Types of tests to generate (default: ["basic", "contract"])
            output_file: File to write test class to (optional)

        Returns:
            Generated test class code as string
        """
        if test_types is None:
            test_types = ["basic", "contract"]

        class_name = f"Test{component_class.__name__}"
        component_name = component_class.__name__

        # Generate imports
        imports = self._generate_imports(component_class)

        # Generate class header
        class_header = f'''
class {class_name}(ComponentTest):
    """Auto-generated integration tests for {component_name}."""

    component_class = {component_name}

    # Override these in your test class for custom behavior
    default_inputs = {{}}
    required_env_vars = []
    requires_api_key = False
'''

        # Generate test methods
        test_methods = []
        for test_type in test_types:
            if test_type in self.test_templates:
                method_code = self.test_templates[test_type](component_class)
                test_methods.append(method_code)

        # Combine all parts
        full_code = imports + class_header + "\n".join(test_methods)

        # Write to file if specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(full_code)

        return full_code

    def _generate_imports(self, component_class: type[Component]) -> str:
        """Generate import statements for the test."""
        module_path = component_class.__module__

        return f'''"""Auto-generated integration tests."""

from tests.integration.framework import ComponentTest, requires_api_key, skip_if_no_env
from {module_path} import {component_class.__name__}

'''

    def _generate_basic_test(self, component_class: type[Component]) -> str:
        """Generate basic functionality test."""
        return '''
    def test_component_initialization(self):
        """Test component can be initialized properly."""
        component = self.component_instance
        assert component is not None
        assert hasattr(component, 'inputs')
        assert hasattr(component, 'outputs')

    async def test_component_basic_execution(self):
        """Test component basic execution."""
        # This is a basic test - customize for your component's specific behavior
        try:
            result = await self.run_component(inputs={}, run_input="test")
            assert result is not None
            # Add specific assertions for your component's outputs
        except Exception as e:
            # Some components may require specific inputs
            assert "required" in str(e).lower() or "missing" in str(e).lower()
'''

    def _generate_contract_test(self, component_class: type[Component]) -> str:
        """Generate component contract test."""
        # Analyze component to get expected inputs/outputs
        component_instance = component_class()

        input_names = [inp.name for inp in component_instance.inputs] if hasattr(component_instance, "inputs") else []
        output_names = (
            [out.name for out in component_instance.outputs] if hasattr(component_instance, "outputs") else []
        )

        expected_inputs_str = str(input_names) if input_names else "[]"
        expected_outputs_str = str(output_names) if output_names else "[]"

        return f'''
    def test_component_contract(self):
        """Test component follows expected contract."""
        component = self.component_instance

        # Test component structure
        self.assertions.assert_component_contract(
            component,
            expected_inputs={expected_inputs_str},
            expected_outputs={expected_outputs_str}
        )

        # Test component metadata
        assert hasattr(component, 'display_name')
        assert hasattr(component, 'description')
        assert component.display_name is not None
        assert component.description is not None
'''

    def _generate_error_test(self, component_class: type[Component]) -> str:
        """Generate error handling test."""
        return '''
    async def test_component_error_handling(self):
        """Test component handles errors gracefully."""
        # Test with invalid inputs
        try:
            result = await self.run_component(inputs={"invalid_param": "value"})
            # If no error, component should still produce valid output
            assert result is not None
        except Exception as e:
            # Error should be informative
            error_msg = str(e)
            assert len(error_msg) > 0
            assert not error_msg.startswith("'NoneType'")

    async def test_component_empty_input(self):
        """Test component with empty input."""
        try:
            result = await self.run_component(inputs={}, run_input="")
            assert result is not None
        except Exception as e:
            # Empty input errors are acceptable
            assert isinstance(e, (ValueError, TypeError, AttributeError))
'''

    def _generate_performance_test(self, component_class: type[Component]) -> str:
        """Generate performance test."""
        return '''
    async def test_component_performance(self):
        """Test component performance meets basic requirements."""
        import time

        start_time = time.time()

        try:
            result = await self.run_component(inputs={}, run_input="performance test")
            execution_time = time.time() - start_time

            # Basic performance assertion - adjust as needed
            self.assertions.assert_performance(
                execution_time,
                max_time=30.0,  # 30 second timeout
                operation_name=f"{self.component_class.__name__} execution"
            )

        except Exception as e:
            # Performance test shouldn't fail due to component errors
            execution_time = time.time() - start_time

            # Even failed executions should complete in reasonable time
            assert execution_time < 60.0, f"Component took too long to fail: {execution_time:.2f}s"
'''

    def discover_components(self, module_path: str) -> list[type[Component]]:
        """Discover all Component classes in a module path.

        Args:
            module_path: Python module path (e.g., "langflow.components.inputs")

        Returns:
            List of discovered Component classes
        """
        try:
            import importlib

            module = importlib.import_module(module_path)

            components = []
            for name in dir(module):
                obj = getattr(module, name)
                if inspect.isclass(obj) and issubclass(obj, Component) and obj != Component:
                    components.append(obj)

            return components

        except ImportError:
            return []

    def generate_tests_for_module(self, module_path: str, output_dir: str, test_types: list[str] | None = None):
        """Generate tests for all components in a module.

        Args:
            module_path: Python module path to discover components
            output_dir: Directory to write test files
            test_types: Types of tests to generate
        """
        components = self.discover_components(module_path)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for component_class in components:
            test_filename = f"test_{component_class.__name__.lower()}_generated.py"
            test_file_path = output_path / test_filename

            self.generate_test_class(component_class, test_types=test_types, output_file=str(test_file_path))


class FlowTestGenerator:
    """Generates integration tests for common flow patterns."""

    def __init__(self):
        self.flow_patterns = {
            "linear": self._generate_linear_flow_test,
            "parallel": self._generate_parallel_flow_test,
            "conditional": self._generate_conditional_flow_test,
        }

    def generate_flow_test(
        self, flow_name: str, components: list[type[Component]], pattern: str = "linear", output_file: str | None = None
    ) -> str:
        """Generate a flow test for given components.

        Args:
            flow_name: Name for the flow test
            components: List of component classes to use in flow
            pattern: Flow pattern ("linear", "parallel", "conditional")
            output_file: File to write test to (optional)

        Returns:
            Generated test code as string
        """
        if pattern not in self.flow_patterns:
            msg = f"Unknown flow pattern: {pattern}. Available: {list(self.flow_patterns.keys())}"
            raise ValueError(msg)

        test_code = self.flow_patterns[pattern](flow_name, components)

        if output_file:
            with open(output_file, "w") as f:
                f.write(test_code)

        return test_code

    def _generate_linear_flow_test(self, flow_name: str, components: list[type[Component]]) -> str:
        """Generate test for linear flow."""
        component_imports = []
        component_names = []

        for component_class in components:
            module_path = component_class.__module__
            component_name = component_class.__name__
            component_imports.append(f"from {module_path} import {component_name}")
            component_names.append(component_name)

        imports_str = "\n".join(component_imports)
        components_list_str = ", ".join(component_names)

        return f'''"""Auto-generated flow test for {flow_name}."""

from tests.integration.framework import FlowTest
from langflow.graph import Graph
{imports_str}


class Test{flow_name}Flow(FlowTest):
    """Test {flow_name} linear flow."""

    def build_flow(self) -> Graph:
        """Build linear flow with components: {components_list_str}."""
        components = [{components_list_str}]
        return self.runner.build_linear_flow(components)

    async def test_flow_execution(self):
        """Test flow executes successfully."""
        result = await self.run_flow(run_input="test input")

        # Basic assertions - customize for your specific flow
        self.assert_message_in_outputs(result, "test input")

    async def test_flow_with_multiple_inputs(self):
        """Test flow with various inputs."""
        test_inputs = ["hello", "test", "example input"]

        for test_input in test_inputs:
            result = await self.run_flow(run_input=test_input)
            assert result is not None
            # Add specific assertions for your flow
'''

    def _generate_parallel_flow_test(self, flow_name: str, components: list[type[Component]]) -> str:
        """Generate test for parallel flow."""
        # This would generate a more complex parallel flow test
        return f'''"""Auto-generated parallel flow test for {flow_name}."""

# TODO: Implement parallel flow test generation
# This would create a flow where multiple components process the same input in parallel
'''

    def _generate_conditional_flow_test(self, flow_name: str, components: list[type[Component]]) -> str:
        """Generate test for conditional flow."""
        # This would generate a conditional flow test
        return f'''"""Auto-generated conditional flow test for {flow_name}."""

# TODO: Implement conditional flow test generation
# This would create a flow with conditional routing based on input
'''


class TestDiscovery:
    """Discovers existing tests and suggests improvements."""

    def __init__(self, test_directory: str):
        self.test_directory = Path(test_directory)

    def find_untested_components(self, component_modules: list[str]) -> list[type[Component]]:
        """Find components that don't have integration tests.

        Args:
            component_modules: List of module paths to check

        Returns:
            List of component classes without tests
        """
        generator = ComponentTestGenerator()
        all_components = []

        for module_path in component_modules:
            components = generator.discover_components(module_path)
            all_components.extend(components)

        # Find existing test files
        existing_test_files = list(self.test_directory.glob("**/test_*.py"))
        existing_test_names = set()

        for test_file in existing_test_files:
            with open(test_file) as f:
                content = f.read()
                # Simple heuristic: look for class names in test files
                for component in all_components:
                    if component.__name__ in content:
                        existing_test_names.add(component.__name__)

        # Find untested components
        untested_components = []
        for component in all_components:
            if component.__name__ not in existing_test_names:
                untested_components.append(component)

        return untested_components

    def analyze_test_coverage(self, test_file: str) -> dict[str, Any]:
        """Analyze test coverage for a specific test file.

        Args:
            test_file: Path to test file

        Returns:
            Dictionary with coverage analysis
        """
        test_path = Path(test_file)
        if not test_path.exists():
            return {"error": "Test file not found"}

        with open(test_path) as f:
            content = f.read()

        # Count test methods
        test_methods = [line for line in content.split("\n") if line.strip().startswith("def test_")]

        # Look for common test patterns
        patterns = {
            "async_tests": "async def test_" in content,
            "parametrized_tests": "@pytest.mark.parametrize" in content,
            "error_handling": "pytest.raises" in content or "Exception" in content,
            "performance_tests": "time." in content or "performance" in content.lower(),
            "api_key_tests": "api_key_required" in content,
            "mock_usage": "mock" in content.lower() or "Mock" in content,
        }

        return {
            "file": str(test_path),
            "test_method_count": len(test_methods),
            "test_methods": [method.strip() for method in test_methods],
            "patterns": patterns,
            "line_count": len(content.split("\n")),
        }

    def suggest_missing_tests(self, component_class: type[Component]) -> list[str]:
        """Suggest types of tests that might be missing for a component.

        Args:
            component_class: Component class to analyze

        Returns:
            List of suggested test types
        """
        suggestions = []

        # Analyze component characteristics
        component_instance = component_class()

        # Check if component has async methods
        async_methods = [
            name
            for name, method in inspect.getmembers(component_instance, inspect.ismethod)
            if inspect.iscoroutinefunction(method)
        ]

        if async_methods:
            suggestions.append("async_execution_tests")

        # Check if component has multiple inputs/outputs
        if hasattr(component_instance, "inputs") and len(component_instance.inputs) > 2:
            suggestions.append("input_validation_tests")

        if hasattr(component_instance, "outputs") and len(component_instance.outputs) > 1:
            suggestions.append("output_validation_tests")

        # Check component metadata for hints
        description = getattr(component_instance, "description", "").lower()

        if any(word in description for word in ["api", "request", "http"]):
            suggestions.append("api_integration_tests")
            suggestions.append("error_handling_tests")
            suggestions.append("timeout_tests")

        if any(word in description for word in ["file", "save", "load", "read", "write"]):
            suggestions.append("file_operation_tests")
            suggestions.append("permission_tests")

        if any(word in description for word in ["llm", "model", "ai", "generate"]):
            suggestions.append("model_response_tests")
            suggestions.append("token_usage_tests")

        # Always suggest basic tests
        suggestions.extend(["initialization_tests", "contract_validation_tests", "error_handling_tests"])

        return list(set(suggestions))  # Remove duplicates
