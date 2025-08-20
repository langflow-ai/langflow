"""Langflow Integration Test Framework.

This package provides a simplified and powerful framework for writing integration tests
in Langflow. It includes base classes, utilities, and decorators that make it easy to:

- Test individual components with minimal boilerplate
- Create end-to-end flow tests
- Mock external dependencies automatically
- Generate tests from component definitions
- Validate component contracts and schemas

Example Usage:
    from tests.integration.framework import ComponentTest, FlowTest

    class TestChatInput(ComponentTest):
        component_class = ChatInput

        def test_basic_functionality(self):
            result = self.run_component(input_text="Hello")
            self.assert_message_output(result, "Hello")
"""

from .assertions import AssertionHelpers
from .base import ComponentTest, FlowTest, IntegrationTestCase
from .decorators import auto_cleanup, leak_detection, requires_api_key, skip_if_no_env, timeout
from .fixtures import MockComponentFactory, TestDataFactory
from .generators import ComponentTestGenerator, FlowTestGenerator
from .runners import APITestRunner, ComponentRunner, FlowRunner

__all__ = [
    "APITestRunner",
    # Utilities
    "AssertionHelpers",
    "ComponentRunner",
    # Base classes
    "ComponentTest",
    "ComponentTestGenerator",
    "FlowRunner",
    "FlowTest",
    "FlowTestGenerator",
    "IntegrationTestCase",
    "MockComponentFactory",
    "TestDataFactory",
    "auto_cleanup",
    "leak_detection",
    # Decorators
    "requires_api_key",
    "skip_if_no_env",
    "timeout",
]
