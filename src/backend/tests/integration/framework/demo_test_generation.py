#!/usr/bin/env python3
"""Demonstration of automatic test generation capabilities."""

import sys
from pathlib import Path

# Add framework to path
framework_path = Path(__file__).parent
sys.path.insert(0, str(framework_path))

from generators import ComponentTestGenerator, FlowTestGenerator, TestDiscovery


class MockChatInput:
    """Mock ChatInput component for demonstration."""

    display_name = "Chat Input"
    description = "Accepts user input and creates a message"
    name = "ChatInput"

    def __init__(self):
        self.inputs = [
            MockInput("input_value", "str", "Input Value"),
            MockInput("sender", "str", "Sender"),
            MockInput("sender_name", "str", "Sender Name"),
        ]
        self.outputs = [MockOutput("message", "Message", "Chat Message")]


class MockLLMComponent:
    """Mock LLM component for demonstration."""

    display_name = "OpenAI LLM"
    description = "LLM component that generates responses using OpenAI API"
    name = "OpenAIComponent"

    def __init__(self):
        self.inputs = [
            MockInput("input_value", "Message", "Input Message"),
            MockInput("api_key", "str", "API Key"),
            MockInput("model", "str", "Model Name"),
            MockInput("temperature", "float", "Temperature"),
        ]
        self.outputs = [MockOutput("text", "Message", "Generated Text")]


class MockInput:
    def __init__(self, name: str, input_type: str, display_name: str = ""):
        self.name = name
        self.type = input_type
        self.display_name = display_name or name.title()


class MockOutput:
    def __init__(self, name: str, output_type: str, display_name: str = ""):
        self.name = name
        self.type = output_type
        self.display_name = display_name or name.title()


def demo_component_test_generation():
    """Demonstrate automatic component test generation."""
    print("🧪 Component Test Generation Demo")
    print("=" * 50)

    generator = ComponentTestGenerator()

    # Generate basic test for ChatInput
    print("📝 Generating BASIC test for ChatInput...")
    basic_test = generator.generate_test_class(MockChatInput, test_types=["basic"], output_file=None)

    print("Generated test code:")
    print("-" * 30)
    print(basic_test[:800] + "..." if len(basic_test) > 800 else basic_test)
    print("-" * 30)

    # Generate comprehensive test suite
    print("\n📋 Generating COMPREHENSIVE test suite for LLM Component...")
    comprehensive_test = generator.generate_test_class(
        MockLLMComponent, test_types=["basic", "contract", "error_handling", "performance"], output_file=None
    )

    print("Generated comprehensive test (first 1000 chars):")
    print("-" * 30)
    print(comprehensive_test[:1000] + "..." if len(comprehensive_test) > 1000 else comprehensive_test)
    print("-" * 30)

    # Show what test types are available
    print(f"\n🎯 Available test types: {list(generator.test_templates.keys())}")

    return basic_test, comprehensive_test


def demo_flow_test_generation():
    """Demonstrate automatic flow test generation."""
    print("\n\n🔄 Flow Test Generation Demo")
    print("=" * 50)

    generator = FlowTestGenerator()

    # Generate linear flow test
    print("📝 Generating LINEAR flow test...")
    flow_components = [MockChatInput, MockLLMComponent]

    linear_flow_test = generator.generate_flow_test(
        flow_name="ChatWithLLM", components=flow_components, pattern="linear"
    )

    print("Generated flow test code:")
    print("-" * 30)
    print(linear_flow_test[:1200] + "..." if len(linear_flow_test) > 1200 else linear_flow_test)
    print("-" * 30)

    print(f"\n🎯 Available flow patterns: {list(generator.flow_patterns.keys())}")

    return linear_flow_test


def demo_test_discovery():
    """Demonstrate test discovery capabilities."""
    print("\n\n🔍 Test Discovery Demo")
    print("=" * 50)

    # Create discovery instance
    discovery = TestDiscovery("tests/integration")

    # Mock some components as "discovered"
    mock_components = [MockChatInput, MockLLMComponent]

    print("📋 Analyzing mock components for missing tests...")

    for component_class in mock_components:
        print(f"\n🔎 Component: {component_class.display_name}")

        # Get test suggestions
        suggestions = discovery.suggest_missing_tests(component_class)
        print(f"   📝 Suggested test types: {suggestions[:5]}...")  # Show first 5

        # Mock test coverage analysis
        mock_analysis = {
            "file": f"test_{component_class.name.lower()}.py",
            "test_method_count": 3,
            "test_methods": ["test_initialization", "test_basic_execution", "test_error_handling"],
            "patterns": {
                "async_tests": True,
                "parametrized_tests": False,
                "error_handling": True,
                "performance_tests": False,
                "api_key_tests": "api" in component_class.description.lower(),
                "mock_usage": True,
            },
            "line_count": 85,
        }

        print("   📊 Mock coverage analysis:")
        print(f"      - Test methods: {mock_analysis['test_method_count']}")
        print(f"      - Lines of code: {mock_analysis['line_count']}")
        print(f"      - Has async tests: {mock_analysis['patterns']['async_tests']}")
        print(f"      - Has API key tests: {mock_analysis['patterns']['api_key_tests']}")
        print(f"      - Missing patterns: {[k for k, v in mock_analysis['patterns'].items() if not v]}")


def save_generated_tests():
    """Save generated tests to files for inspection."""
    print("\n\n💾 Saving Generated Tests")
    print("=" * 50)

    generator = ComponentTestGenerator()

    # Save ChatInput test
    output_dir = Path("generated_tests")
    output_dir.mkdir(exist_ok=True)

    chat_input_test = generator.generate_test_class(
        MockChatInput, test_types=["basic", "contract"], output_file=str(output_dir / "test_chat_input_generated.py")
    )

    # Save LLM Component test
    llm_test = generator.generate_test_class(
        MockLLMComponent,
        test_types=["basic", "contract", "error_handling"],
        output_file=str(output_dir / "test_llm_component_generated.py"),
    )

    print("✅ Generated tests saved to:")
    print(f"   - {output_dir / 'test_chat_input_generated.py'}")
    print(f"   - {output_dir / 'test_llm_component_generated.py'}")

    # Also save flow test
    flow_generator = FlowTestGenerator()
    flow_test = flow_generator.generate_flow_test(
        "ChatLLMFlow",
        [MockChatInput, MockLLMComponent],
        pattern="linear",
        output_file=str(output_dir / "test_flow_generated.py"),
    )

    print(f"   - {output_dir / 'test_flow_generated.py'}")

    return output_dir


def main():
    """Run all generation demos."""
    print("🚀 Integration Test Framework - Generation Capabilities Demo")
    print("=" * 70)

    try:
        # Demo component test generation
        basic_test, comprehensive_test = demo_component_test_generation()

        # Demo flow test generation
        flow_test = demo_flow_test_generation()

        # Demo test discovery
        demo_test_discovery()

        # Save examples
        output_dir = save_generated_tests()

        print("\n\n🎉 Generation Demo Complete!")
        print("=" * 70)
        print("\n📋 Summary of Capabilities:")
        print("✅ Component Test Generation:")
        print("   - Basic functionality tests")
        print("   - Contract validation tests")
        print("   - Error handling tests")
        print("   - Performance tests")
        print("   - Custom test combinations")

        print("\n✅ Flow Test Generation:")
        print("   - Linear flow patterns")
        print("   - Multi-component chains")
        print("   - End-to-end validation")
        print("   - Custom flow patterns (extensible)")

        print("\n✅ Test Discovery:")
        print("   - Find untested components")
        print("   - Analyze existing test coverage")
        print("   - Suggest missing test types")
        print("   - Gap analysis and recommendations")

        print(f"\n📁 Generated test files available in: {output_dir}")
        print("\n🎯 The framework can generate tests for:")
        print("   • Individual Components (any Langflow component)")
        print("   • Complete Flows (multi-component workflows)")
        print("   • API Endpoints (REST API integration tests)")
        print("   • Custom Test Patterns (extensible generators)")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
