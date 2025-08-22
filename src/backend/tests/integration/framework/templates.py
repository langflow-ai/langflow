"""Template generator for integration tests.

This module provides templates that engineers can copy and customize for their integration tests.
No complex framework - just simple copy-paste templates.

Supports all component categories: inputs, outputs, processing, helpers, agents, vectorstores, etc.
"""

# Basic component test template - works for most components
COMPONENT_TEST_TEMPLATE = '''"""Integration tests for {component_name} component."""

from langflow.components.{module_path} import {component_class}
from langflow.schema.message import Message
from langflow.schema.data import Data

from tests.integration.utils import pyleak_marker, run_single_component

# Add memory leak detection to all tests in this file
pytestmark = pyleak_marker()


async def test_default():
    """Test component with default inputs."""
    outputs = await run_single_component({component_class}, run_input="hello")

    # Add your assertions here based on component outputs
    assert outputs is not None
    # Common output types to check:
    # assert "message" in outputs and isinstance(outputs["message"], Message)
    # assert "data" in outputs and isinstance(outputs["data"], list)
    # assert "prompt" in outputs and isinstance(outputs["prompt"], Message)


async def test_with_inputs():
    """Test component with custom inputs."""
    inputs = {{
        # Add your component-specific inputs here
        # "template": "Hello {{var1}}",
        # "var1": "World",
        # "sender": "Bot",
        # "query": ".key",
    }}
    outputs = await run_single_component({component_class}, inputs=inputs, run_input="test")

    assert outputs is not None
    # Add your specific assertions based on component behavior


async def test_empty_input():
    """Test component handles empty input gracefully."""
    outputs = await run_single_component({component_class}, run_input="")

    assert outputs is not None
    # Add assertions for empty input behavior


async def test_with_session():
    """Test component with session ID."""
    session_id = "test-session-123"
    outputs = await run_single_component(
        {component_class},
        run_input="session test",
        session_id=session_id
    )

    assert outputs is not None
    # Add session-related assertions if component supports sessions
'''

FLOW_TEST_TEMPLATE = '''"""Integration tests for {flow_name} flow."""

from langflow.components.{input_module} import {input_component}
from langflow.components.{output_module} import {output_component}
from langflow.graph import Graph
from langflow.schema.message import Message

from tests.integration.utils import pyleak_marker, run_flow

# Add memory leak detection to all tests in this file
pytestmark = pyleak_marker()


async def test_simple_flow():
    """Test basic flow: Input -> Processing -> Output."""
    graph = Graph()

    # Add components to graph
    input_comp = graph.add_component({input_component}())
    output_comp = graph.add_component({output_component}())

    # Add your processing components here
    # process_comp = graph.add_component(SomeProcessor())

    # Connect components
    graph.add_component_edge(input_comp, ("message", "input_value"), output_comp)

    # Run the flow
    outputs = await run_flow(graph, run_input="test message")

    # Add your assertions
    assert outputs is not None
    assert "message" in outputs
    # assert isinstance(outputs["message"], Message)


async def test_complex_flow():
    """Test multi-step flow."""
    graph = Graph()

    # Build your flow here
    # component1 = graph.add_component(Component1())
    # component2 = graph.add_component(Component2())
    # component3 = graph.add_component(Component3())

    # Connect them
    # graph.add_component_edge(component1, ("output", "input"), component2)
    # graph.add_component_edge(component2, ("output", "input"), component3)

    # outputs = await run_flow(graph, run_input="complex test")
    # assert outputs is not None


async def test_flow_with_session():
    """Test flow with custom session ID."""
    graph = Graph()

    # Build simple flow
    input_comp = graph.add_component({input_component}())
    output_comp = graph.add_component({output_component}())
    graph.add_component_edge(input_comp, ("message", "input_value"), output_comp)

    session_id = "flow-session-456"
    outputs = await run_flow(graph, run_input="session test", session_id=session_id)

    assert outputs is not None
    # Add session-related assertions
'''


def generate_component_test(component_name: str, component_class: str, module_path: str) -> str:
    """Generate a component test file."""
    return COMPONENT_TEST_TEMPLATE.format(
        component_name=component_name, component_class=component_class, module_path=module_path
    )


def generate_flow_test(
    flow_name: str, input_component: str, input_module: str, output_component: str, output_module: str
) -> str:
    """Generate a flow test file."""
    return FLOW_TEST_TEMPLATE.format(
        flow_name=flow_name,
        input_component=input_component,
        input_module=input_module,
        output_component=output_component,
        output_module=output_module,
    )


# Specialized templates for different component types

# Template for components that use ComponentInputHandle (like helpers)
HELPER_COMPONENT_TEMPLATE = '''"""Integration tests for {component_name} component."""

import pytest
from langflow.components.{module_path} import {component_class}
from langflow.components.input_output import ChatInput
from langflow.schema.data import Data

from tests.integration.components.mock_components import TextToData
from tests.integration.utils import ComponentInputHandle, pyleak_marker, run_single_component

pytestmark = pyleak_marker()


async def test_from_data():
    """Test component with Data input."""
    outputs = await run_single_component(
        {component_class},
        inputs={{
            "input_value": ComponentInputHandle(
                clazz=TextToData,
                inputs={{"text_data": ['test data'], "is_json": False}},
                output_name="from_text"
            ),
            # Add other component-specific inputs here
            # "query": ".key",
            # "template": "Hello {{var1}}",
        }},
    )
    assert outputs is not None
    # Add your specific assertions


async def test_from_message():
    """Test component with Message input."""
    outputs = await run_single_component(
        {component_class},
        inputs={{
            "input_value": ComponentInputHandle(
                clazz=ChatInput,
                inputs={{}},
                output_name="message"
            ),
            # Add other inputs here
        }},
        run_input="test message",
    )
    assert outputs is not None
    # Add your specific assertions
'''

# Template for components that need API keys or external services
API_COMPONENT_TEMPLATE = '''"""Integration tests for {component_name} component."""

import os
import pytest
from langflow.components.{module_path} import {component_class}

from tests.api_keys import get_openai_api_key  # Adjust import as needed
from tests.integration.utils import pyleak_marker, run_single_component

pytestmark = pyleak_marker()


@pytest.mark.skipif(not get_openai_api_key(), reason="API key not available")
async def test_with_api_key():
    """Test component with API key."""
    inputs = {{
        "api_key": get_openai_api_key(),
        # Add other component-specific inputs here
    }}
    outputs = await run_single_component({component_class}, inputs=inputs, run_input="test")

    assert outputs is not None
    # Add your specific assertions


async def test_without_api_key():
    """Test component fails gracefully without API key."""
    with pytest.raises((ValueError, Exception)):
        await run_single_component({component_class}, run_input="test")
'''

# Template for agent components that might have special error handling
AGENT_COMPONENT_TEMPLATE = '''"""Integration tests for {component_name} component."""

import pytest
from langflow.components.{module_path} import {component_class}

from tests.integration.utils import run_single_component

# TODO: Add more tests for {component_class}
@pytest.mark.asyncio
async def test_{component_name_lower}():
    """Test {component_name} component."""
    inputs = {{
        # Add component-specific inputs here
    }}

    # Expect an error from this call if inputs are incomplete
    with pytest.raises((ValueError, Exception), match=".*"):
        await run_single_component(
            {component_class},
            inputs=inputs,
        )

    # Add successful test cases with proper inputs:
    # inputs_success = {{
    #     "required_param": "value",
    # }}
    # outputs = await run_single_component({component_class}, inputs=inputs_success)
    # assert outputs is not None
'''

# Template for simple processing components (like prompts)
PROCESSING_COMPONENT_TEMPLATE = '''"""Integration tests for {component_name} component."""

from langflow.components.{module_path} import {component_class}
from langflow.schema.message import Message

from tests.integration.utils import pyleak_marker, run_single_component

pytestmark = pyleak_marker()


async def test_basic_processing():
    """Test basic component processing."""
    outputs = await run_single_component(
        {component_class},
        inputs={{
            # Add component-specific inputs
            # "template": "Hello {{var1}}",
            # "var1": "World",
        }}
    )
    assert outputs is not None
    # Common assertions for processing components:
    # assert isinstance(outputs["prompt"], Message)
    # assert outputs["prompt"].text == "expected output"
'''

# Pre-made templates for common components
CHAT_INPUT_TEST = generate_component_test("ChatInput", "ChatInput", "input_output")

CHAT_OUTPUT_TEST = generate_component_test("ChatOutput", "ChatOutput", "input_output")

PROMPT_TEST = PROCESSING_COMPONENT_TEMPLATE.format(
    component_name="Prompt", component_class="PromptComponent", module_path="processing"
)

BASIC_FLOW_TEST = generate_flow_test("Basic", "ChatInput", "input_output", "ChatOutput", "input_output")
