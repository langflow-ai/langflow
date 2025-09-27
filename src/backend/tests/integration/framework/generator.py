"""Simple test generator for integration tests.

Usage:
    from tests.integration.framework.generator import generate_test

    # Generate component test
    test_code = generate_test("component", "MyComponent", "my_module")

    # Generate flow test
    test_code = generate_test("flow", "MyFlow")
"""

import argparse
from pathlib import Path

from .templates import (
    AGENT_COMPONENT_TEMPLATE,
    API_COMPONENT_TEMPLATE,
    COMPONENT_TEST_TEMPLATE,
    HELPER_COMPONENT_TEMPLATE,
    PROCESSING_COMPONENT_TEMPLATE,
    generate_flow_test,
)


def generate_test(test_type: str, name: str, template_type: str = "basic", **kwargs) -> str:
    """Generate test code based on type and parameters.

    Args:
        test_type: "component" or "flow"
        name: Name of the component or flow
        template_type: Type of template for components:
            - "basic": Basic component test (default)
            - "helper": For components using ComponentInputHandle
            - "api": For components needing API keys
            - "agent": For agent components with error handling
            - "processing": For simple processing components
        **kwargs: Additional parameters for template

    Returns:
        Generated test code as string
    """
    if test_type == "component":
        # Select template based on component category/type
        template_map = {
            "basic": COMPONENT_TEST_TEMPLATE,
            "helper": HELPER_COMPONENT_TEMPLATE,
            "api": API_COMPONENT_TEMPLATE,
            "agent": AGENT_COMPONENT_TEMPLATE,
            "processing": PROCESSING_COMPONENT_TEMPLATE,
        }

        template = template_map.get(template_type, COMPONENT_TEST_TEMPLATE)

        return template.format(
            component_name=name,
            component_name_lower=name.lower().replace(" ", "_"),
            component_class=kwargs.get("component_class", name),
            module_path=kwargs.get("module_path", "input_output"),
        )
    if test_type == "flow":
        return generate_flow_test(
            flow_name=name,
            input_component=kwargs.get("input_component", "ChatInput"),
            input_module=kwargs.get("input_module", "input_output"),
            output_component=kwargs.get("output_component", "ChatOutput"),
            output_module=kwargs.get("output_module", "input_output"),
        )
    error_msg = f"Unknown test type: {test_type}"
    raise ValueError(error_msg)


def create_test_file(output_path: Path, test_code: str) -> None:
    """Create a test file with the generated code."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(test_code)
    msg = f"Generated test file: {output_path}"
    print(msg)  # noqa: T201


def main():
    """Command line interface for generating tests."""
    parser = argparse.ArgumentParser(description="Generate Langflow integration tests")
    parser.add_argument("type", choices=["component", "flow"], help="Type of test to generate")
    parser.add_argument("name", help="Name of component or flow")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument(
        "--template",
        choices=["basic", "helper", "api", "agent", "processing"],
        default="basic",
        help="Template type for component tests",
    )
    parser.add_argument("--component-class", help="Component class name (for component tests)")
    parser.add_argument("--module-path", help="Module path (for component tests)")

    args = parser.parse_args()

    # Generate test code
    kwargs = {}
    if args.component_class:
        kwargs["component_class"] = args.component_class
    if args.module_path:
        kwargs["module_path"] = args.module_path

    test_code = generate_test(args.type, args.name, args.template, **kwargs)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        filename = f"test_{args.name.lower().replace(' ', '_')}_{args.type}.py"
        output_path = Path(f"tests/integration/{args.type}s/{filename}")

    # Create the test file
    create_test_file(output_path, test_code)


if __name__ == "__main__":
    main()
