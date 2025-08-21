#!/usr/bin/env python3
"""Demonstration of automatic test generation capabilities."""

import sys
from pathlib import Path

# Add framework to path
framework_path = Path(__file__).parent
sys.path.insert(0, str(framework_path))

from generators import ComponentTestGenerator, FlowTestGenerator, TestDiscovery


class MockComponent:
    """Mock component for demonstration."""

    def __init__(self, name: str, description: str, inputs: list, outputs: list):
        self.display_name = name
        self.description = description
        self.name = name.replace(" ", "")
        self.inputs = [MockIO(i["name"], i["type"]) for i in inputs]
        self.outputs = [MockIO(o["name"], o["type"]) for o in outputs]


class MockIO:
    """Mock input/output for demonstration."""

    def __init__(self, name: str, io_type: str):
        self.name = name
        self.type = io_type
        self.display_name = name.title()


def demo_generation_capabilities():
    """Demonstrate core generation capabilities concisely."""
    print("🧪 Framework Generation Demo")
    print("=" * 40)

    # Create mock components
    chat_input = MockComponent(
        "Chat Input",
        "User input component",
        [{"name": "input_value", "type": "str"}],
        [{"name": "message", "type": "Message"}],
    )

    llm_component = MockComponent(
        "LLM",
        "LLM API component",
        [{"name": "input_value", "type": "Message"}, {"name": "api_key", "type": "str"}],
        [{"name": "text", "type": "Message"}],
    )

    # Demo component generation
    generator = ComponentTestGenerator()
    basic_test = generator.generate_test_class(chat_input, test_types=["basic"], output_file=None)
    print(f"✓ Generated component test ({len(basic_test)} chars)")
    print(f"  Available types: {list(generator.test_templates.keys())}")

    # Demo flow generation
    flow_generator = FlowTestGenerator()
    flow_test = flow_generator.generate_flow_test("ChatFlow", [chat_input, llm_component], "linear")
    print(f"✓ Generated flow test ({len(flow_test)} chars)")
    print(f"  Available patterns: {list(flow_generator.flow_patterns.keys())}")

    # Demo discovery
    discovery = TestDiscovery("tests/integration")
    suggestions = discovery.suggest_missing_tests(llm_component)
    print(f"✓ Generated test suggestions: {suggestions[:3]}...")

    return basic_test, flow_test


def main():
    """Run generation demo."""
    print("🚀 Integration Test Framework Demo")
    print("=" * 40)

    try:
        basic_test, flow_test = demo_generation_capabilities()

        print("\n✅ Demo Complete!")
        print("Framework can generate:")
        print("• Component tests (basic, contract, error, performance)")
        print("• Flow tests (linear, parallel, conditional)")
        print("• Test discovery and gap analysis")

    except Exception as e:
        print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    main()
