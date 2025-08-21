"""Simple demo showing integration test framework usage without dependencies."""

import pytest


class MockComponent:
    """Mock component for demonstration purposes."""

    display_name = "Mock Component"
    description = "A simple mock component for testing"
    name = "MockComponent"

    def __init__(self):
        self.inputs = [MockInput("test_input", "str")]
        self.outputs = [MockOutput("test_output", "str")]

    async def build(self, test_input: str) -> str:
        return f"Processed: {test_input}"


class MockInput:
    def __init__(self, name: str, input_type: str):
        self.name = name
        self.type = input_type


class MockOutput:
    def __init__(self, name: str, output_type: str):
        self.name = name
        self.type = output_type


class MockIntegrationTestCase:
    """Simplified integration test base class for demo."""

    def setup_method(self):
        """Setup method called before each test method."""
        self.session_id = "mock-session-123"
        self.user_id = "mock-user-456"

    def teardown_method(self):
        """Teardown method called after each test method."""


class MockComponentTest(MockIntegrationTestCase):
    """Mock component test base class for demo."""

    component_class = None
    default_inputs = {}
    required_env_vars = []

    @property
    def component_instance(self):
        """Get component instance."""
        if self.component_class is None:
            raise ValueError("component_class must be set in subclass")
        return self.component_class()

    async def run_component(self, inputs=None, run_input=None, **kwargs):
        """Mock component runner."""
        component = self.component_instance
        if hasattr(component, "build"):
            if run_input is not None:
                return {"test_output": await component.build(run_input)}
            if inputs:
                # Use first input parameter
                first_input = next(iter(inputs.values()))
                return {"test_output": await component.build(first_input)}
        return {"test_output": "mock_result"}


# Demonstration test class
class TestMockComponentExample(MockComponentTest):
    """Example test showing framework usage patterns."""

    component_class = MockComponent

    def test_component_initialization(self):
        """Test component can be initialized properly."""
        component = self.component_instance
        assert component is not None
        assert hasattr(component, "inputs")
        assert hasattr(component, "outputs")
        assert component.display_name == "Mock Component"

    async def test_component_basic_execution(self):
        """Test component basic execution."""
        result = await self.run_component(run_input="hello world")

        assert result is not None
        assert "test_output" in result
        assert result["test_output"] == "Processed: hello world"

    def test_component_contract(self):
        """Test component follows expected contract."""
        component = self.component_instance

        # Test component structure
        assert hasattr(component, "display_name")
        assert hasattr(component, "description")
        assert component.display_name is not None
        assert component.description is not None

        # Test inputs/outputs
        assert len(component.inputs) == 1
        assert component.inputs[0].name == "test_input"
        assert len(component.outputs) == 1
        assert component.outputs[0].name == "test_output"

    @pytest.mark.parametrize(
        "test_input,expected_prefix",
        [
            ("hello", "Processed: hello"),
            ("world", "Processed: world"),
            ("test123", "Processed: test123"),
        ],
    )
    async def test_component_with_different_inputs(self, test_input, expected_prefix):
        """Test component with different input values."""
        result = await self.run_component(run_input=test_input)

        assert result["test_output"] == expected_prefix


if __name__ == "__main__":
    # Simple test runner for demonstration
    import asyncio

    async def run_demo():
        print("🚀 Integration Test Framework Demo")
        print("=" * 50)

        # Create test instance
        test = TestMockComponentExample()
        test.setup_method()

        # Run initialization test
        print("✓ Testing component initialization...")
        test.test_component_initialization()
        print("  Component initialized successfully")

        # Run execution test
        print("✓ Testing component execution...")
        await test.test_component_basic_execution()
        print("  Component executed successfully")

        # Run contract test
        print("✓ Testing component contract...")
        test.test_component_contract()
        print("  Component contract verified")

        # Run parametrized tests
        print("✓ Testing with different inputs...")
        test_cases = [
            ("hello", "Processed: hello"),
            ("world", "Processed: world"),
            ("test123", "Processed: test123"),
        ]

        for test_input, expected in test_cases:
            await test.test_component_with_different_inputs(test_input, expected)
            print(f"  ✓ Input '{test_input}' -> '{expected}'")

        test.teardown_method()

        print("\n🎉 All tests passed!")
        print("\nThis demonstrates the integration test framework patterns:")
        print("- Component-based testing with base classes")
        print("- Async test execution support")
        print("- Parametrized testing")
        print("- Contract validation")
        print("- Setup/teardown lifecycle")

    # Run the demo
    asyncio.run(run_demo())
