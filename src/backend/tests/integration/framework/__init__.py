"""Langflow Integration Test Framework.

Simple templates and generators for creating integration tests.

Usage:
    from tests.integration.framework.generator import generate_test
    from tests.integration.framework.templates import CHAT_INPUT_TEST

    # Generate test code
    test_code = generate_test("component", "MyComponent")

    # Use pre-made templates
    print(CHAT_INPUT_TEST)
"""

from .generator import create_test_file, generate_test
from .templates import (
    AGENT_COMPONENT_TEMPLATE,
    API_COMPONENT_TEMPLATE,
    BASIC_FLOW_TEST,
    CHAT_INPUT_TEST,
    CHAT_OUTPUT_TEST,
    COMPONENT_TEST_TEMPLATE,
    HELPER_COMPONENT_TEMPLATE,
    PROCESSING_COMPONENT_TEMPLATE,
    PROMPT_TEST,
    generate_component_test,
    generate_flow_test,
)

__all__ = [
    "AGENT_COMPONENT_TEMPLATE",
    "API_COMPONENT_TEMPLATE",
    "BASIC_FLOW_TEST",
    "CHAT_INPUT_TEST",
    "CHAT_OUTPUT_TEST",
    "COMPONENT_TEST_TEMPLATE",
    "HELPER_COMPONENT_TEMPLATE",
    "PROCESSING_COMPONENT_TEMPLATE",
    "PROMPT_TEST",
    "create_test_file",
    "generate_component_test",
    "generate_flow_test",
    "generate_test",
]
