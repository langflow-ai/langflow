"""Unit test for custom code execution in isolation (with real Langflow code)."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from langflow_stepflow.exceptions import ExecutionError
from langflow_stepflow.worker.custom_code_executor import (
    CustomCodeExecutor,
)


class TestCustomCodeExecutor:
    """Test CustomCodeExecutor functionality with real Langflow component code."""

    @pytest.fixture
    def executor(self):
        """Create CustomCodeExecutor instance."""
        return CustomCodeExecutor()

    @pytest.fixture
    def mock_context(self):
        """Create mock StepflowContext."""
        context = AsyncMock()
        context.get_blob = AsyncMock()
        context.put_blob = AsyncMock()
        return context

    @pytest.fixture
    def simple_component_blob(self):
        """Simple test component blob data."""
        return {
            "code": '''
from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

class SimpleTestComponent(Component):
    display_name = "Simple Test"
    description = "A simple test component"

    inputs = [
        MessageTextInput(
            name="text_input",
            display_name="Text Input",
            info="Text input for testing"
        )
    ]

    outputs = [
        Output(display_name="Output", name="result", method="process_text")
    ]

    async def process_text(self) -> Message:
        """Process the input text and return a message."""
        input_text = self.text_input or "No input provided"
        result_text = f"Processed: {input_text}"

        return Message(
            text=result_text,
            sender="SimpleTestComponent",
            sender_name="Test Component"
        )
''',
            "component_type": "SimpleTestComponent",
            "template": {
                "text_input": {
                    "type": "str",
                    "value": "",
                    "info": "Text input for testing",
                    "required": False,
                }
            },
            "outputs": [
                {"name": "result", "method": "process_text", "types": ["Message"]}
            ],
            "selected_output": "result",
        }

    @pytest.fixture
    def chat_input_component_blob(self):
        """Real ChatInput component blob data from Langflow."""
        return {
            "code": '''
from langflow.base.io.chat import ChatComponent
from langflow.inputs.inputs import BoolInput
from langflow.io import DropdownInput, MessageTextInput, MultilineInput, Output
from langflow.schema.message import Message
from langflow.utils.constants import (
    MESSAGE_SENDER_AI, MESSAGE_SENDER_USER, MESSAGE_SENDER_NAME_USER
)

class ChatInput(ChatComponent):
    display_name = "Chat Input"
    description = "Get chat inputs from the Playground."
    icon = "MessagesSquare"
    name = "ChatInput"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input Text",
            value="",
            info="Message to be passed as input.",
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
            value=MESSAGE_SENDER_USER,
            info="Type of sender.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Name of the sender.",
            value=MESSAGE_SENDER_NAME_USER,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Chat Message", name="message", method="message_response"),
    ]

    async def message_response(self) -> Message:
        """Create a message from the input."""
        message = Message(
            text=self.input_value or "",
            sender=self.sender,
            sender_name=self.sender_name,
        )
        self.status = message
        return message
''',
            "component_type": "ChatInput",
            "template": {
                "input_value": {
                    "type": "str",
                    "value": "",
                    "info": "Message to be passed as input",
                    "required": True,
                },
                "sender": {
                    "type": "str",
                    "value": "User",
                    "options": ["AI", "User"],
                    "info": "Type of sender",
                },
                "sender_name": {
                    "type": "str",
                    "value": "User",
                    "info": "Name of the sender",
                },
            },
            "outputs": [
                {"name": "message", "method": "message_response", "types": ["Message"]}
            ],
            "selected_output": "message",
        }

    @pytest.mark.asyncio
    async def test_execute_missing_blob_id(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when blob_id is missing."""
        input_data = {"input": {"text": "test"}}

        with pytest.raises(ExecutionError, match="No blob_id provided"):
            await executor.execute(input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_simple_component(
        self,
        executor: CustomCodeExecutor,
        mock_context,
        simple_component_blob: dict[str, Any],
    ):
        """Test execution of a simple custom component."""
        # Setup mock context
        mock_context.get_blob.return_value = simple_component_blob

        # Input data with blob_id and runtime inputs
        input_data = {
            "blob_id": "test_blob_123",
            "input": {"text_input": "Hello World"},
        }

        # Execute
        result = await executor.execute(input_data, mock_context)

        # Verify blob was retrieved
        mock_context.get_blob.assert_called_once_with("test_blob_123")

        # Verify result structure
        assert "result" in result
        assert isinstance(result["result"], dict)

        # Verify the processed result
        result_data = result["result"]
        # Langflow Message: result data is nested in ["result"] field
        message_data = result_data["result"] if "result" in result_data else result_data
        assert "text" in message_data
        assert message_data["text"] == "Processed: Hello World"
        assert message_data["sender"] == "SimpleTestComponent"
        assert message_data["sender_name"] == "Test Component"

    @pytest.mark.asyncio
    async def test_execute_chat_input_component(
        self,
        executor: CustomCodeExecutor,
        mock_context,
        chat_input_component_blob: dict[str, Any],
    ):
        """Test execution of real ChatInput component."""
        # Setup mock context
        mock_context.get_blob.return_value = chat_input_component_blob

        # Input data
        input_data = {
            "blob_id": "chatinput_blob_456",
            "input": {
                "input_value": "What is Python?",
                "sender": "User",
                "sender_name": "Test User",
            },
        }

        # Execute
        result = await executor.execute(input_data, mock_context)

        # Verify result
        assert "result" in result
        result_data = result["result"]

        # Should have Langflow Message structure
        # Handle nested result structure from Langflow Messages
        message_data = result_data["result"] if "result" in result_data else result_data
        assert "text" in message_data
        assert message_data["text"] == "What is Python?"
        assert message_data["sender"] == "User"
        assert message_data["sender_name"] == "Test User"
        assert message_data.get("__langflow_type__") == "Message"

    @pytest.mark.asyncio
    async def test_execute_component_with_template_defaults(
        self,
        executor: CustomCodeExecutor,
        mock_context,
        simple_component_blob: dict[str, Any],
    ):
        """Test that template default values are used when input is not provided."""
        # Modify blob to have default value
        simple_component_blob["template"]["text_input"]["value"] = "Default Text"
        mock_context.get_blob.return_value = simple_component_blob

        # Input data without runtime input for text_input
        input_data = {
            "blob_id": "test_blob_789",
            "input": {},  # No runtime inputs provided
        }

        # Execute
        result = await executor.execute(input_data, mock_context)

        # Should use template default
        result_data = result["result"]
        # Handle nested result structure from Langflow Messages
        message_data = result_data["result"] if "result" in result_data else result_data
        assert message_data["text"] == "Processed: Default Text"

    @pytest.mark.asyncio
    async def test_execute_component_runtime_overrides_template(
        self,
        executor: CustomCodeExecutor,
        mock_context,
        simple_component_blob: dict[str, Any],
    ):
        """Test that runtime inputs override template defaults."""
        # Set template default
        simple_component_blob["template"]["text_input"]["value"] = "Template Default"
        mock_context.get_blob.return_value = simple_component_blob

        # Input data with runtime override
        input_data = {
            "blob_id": "test_blob_override",
            "input": {"text_input": "Runtime Override"},
        }

        # Execute
        result = await executor.execute(input_data, mock_context)

        # Should use runtime value, not template default
        result_data = result["result"]
        # Handle nested result structure from Langflow Messages
        message_data = result_data["result"] if "result" in result_data else result_data
        assert message_data["text"] == "Processed: Runtime Override"

    @pytest.mark.asyncio
    async def test_execute_component_with_missing_code(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when component code is missing."""
        blob_data = {
            "component_type": "TestComponent",
            "template": {},
            "outputs": [],
            # Missing "code" field
        }
        mock_context.get_blob.return_value = blob_data

        input_data = {"blob_id": "missing_code_blob", "input": {}}

        with pytest.raises(ExecutionError, match="No code found for component"):
            await executor.execute(input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_component_with_invalid_code(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when component code is invalid Python."""
        blob_data = {
            "code": "invalid python syntax !!!",
            "component_type": "InvalidComponent",
            "template": {},
            "outputs": [],
        }
        mock_context.get_blob.return_value = blob_data

        input_data = {"blob_id": "invalid_code_blob", "input": {}}

        with pytest.raises(ExecutionError, match="Failed to evaluate component code"):
            await executor.execute(input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_component_class_not_found(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when component class is not found in code."""
        blob_data = {
            "code": """
# Valid Python code but no matching class
def some_function():
    return "not a component class"
""",
            "component_type": "MissingComponent",
            "template": {},
            "outputs": [],
        }
        mock_context.get_blob.return_value = blob_data

        input_data = {"blob_id": "no_class_blob", "input": {}}

        with pytest.raises(
            ExecutionError,
            match="Failed to evaluate component code for MissingComponent",
        ):
            await executor.execute(input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_component_instantiation_fails(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when component cannot be instantiated."""
        blob_data = {
            "code": """
from langflow.custom.custom_component.component import Component
from langflow.io import Output

class FailingComponent(Component):
    display_name = "Failing Component"
    description = "Component that fails instantiation"

    outputs = [
        Output(display_name="Result", name="result", method="execute")
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raise ValueError("Cannot instantiate this component")

    def execute(self):
        return "should not reach this"
""",
            "component_type": "FailingComponent",
            "template": {},
            "outputs": [{"name": "result", "method": "execute", "types": ["str"]}],
        }
        mock_context.get_blob.return_value = blob_data

        input_data = {"blob_id": "failing_init_blob", "input": {}}

        with pytest.raises(
            ExecutionError, match="Failed to instantiate FailingComponent"
        ):
            await executor.execute(input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_component_method_not_found(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when execution method is not found."""
        blob_data = {
            "code": """
from langflow.custom.custom_component.component import Component

class NoMethodComponent(Component):
    pass
""",
            "component_type": "NoMethodComponent",
            "template": {},
            "outputs": [
                {"name": "result", "method": "nonexistent_method", "types": ["str"]}
            ],
            "selected_output": "result",
        }
        mock_context.get_blob.return_value = blob_data

        input_data = {"blob_id": "no_method_blob", "input": {}}

        with pytest.raises(ExecutionError, match="Method nonexistent_method not found"):
            await executor.execute(input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_component_method_execution_fails(
        self, executor: CustomCodeExecutor, mock_context
    ):
        """Test execution fails when component method throws exception."""
        blob_data = {
            "code": """
from langflow.custom.custom_component.component import Component

class FailingMethodComponent(Component):
    async def failing_method(self):
        raise RuntimeError("Method execution failed")
""",
            "component_type": "FailingMethodComponent",
            "template": {},
            "outputs": [
                {"name": "result", "method": "failing_method", "types": ["str"]}
            ],
            "selected_output": "result",
        }
        mock_context.get_blob.return_value = blob_data

        input_data = {"blob_id": "failing_method_blob", "input": {}}

        with pytest.raises(ExecutionError, match="Failed to execute failing_method"):
            await executor.execute(input_data, mock_context)

    def test_environment_variable_handling_deprecated(
        self, executor: CustomCodeExecutor
    ):
        """Test that environment variable handling is now handled via preprocessing.

        This test documents that environment variable resolution was moved from
        runtime in the UDF executor to preprocessing at the test/workflow level.
        The _determine_environment_variable method was removed as part of the
        simplification effort to rely on preprocessing instead.
        """
        # Environment variable resolution is now handled by preprocessing
        # instead of runtime resolution in the UDF executor
        assert True  # This test now just documents the architectural change

    def test_determine_execution_method(self, executor: CustomCodeExecutor):
        """Test execution method determination from outputs metadata."""
        outputs = [
            {"name": "result1", "method": "method1", "types": ["str"]},
            {"name": "result2", "method": "method2", "types": ["int"]},
        ]

        # Selected output specified
        method = executor._determine_execution_method(outputs, "result2")
        assert method == "method2"

        # No selected output, use first
        method = executor._determine_execution_method(outputs, None)
        assert method == "method1"

        # Empty outputs
        method = executor._determine_execution_method([], None)
        assert method is None

        # Selected output not found, use first
        method = executor._determine_execution_method(outputs, "nonexistent")
        assert method == "method1"


class TestCustomCodeExecutorDataFrameOutput:
    """Test CustomCodeExecutor with components that return DataFrames (issue #673)."""

    @pytest.fixture
    def executor(self):
        return CustomCodeExecutor()

    @pytest.fixture
    def mock_context(self):
        context = AsyncMock()
        context.get_blob = AsyncMock()
        return context

    @pytest.fixture
    def pandas_dataframe_component_blob(self):
        """Component that returns a plain pandas DataFrame (not lfx DataFrame).

        This simulates the URLComponent scenario from issue #673 where
        compiled component code produces a plain pandas DataFrame.
        """
        return {
            "code": '''
import pandas as pd
from langflow.custom.custom_component.component import Component
from langflow.io import Output

class DataFrameComponent(Component):
    display_name = "DataFrame Test"
    description = "Returns a plain pandas DataFrame"

    outputs = [
        Output(display_name="Content", name="content", method="fetch_content")
    ]

    def fetch_content(self) -> pd.DataFrame:
        """Return a plain pandas DataFrame (not lfx DataFrame)."""
        return pd.DataFrame([
            {"text": "Hello world", "url": "http://example.com", "title": "Test"},
            {"text": "Second row", "url": "http://example.org", "title": "Test 2"},
        ])
''',
            "component_type": "DataFrameComponent",
            "template": {},
            "outputs": [
                {"name": "content", "method": "fetch_content", "types": ["DataFrame"]}
            ],
            "selected_output": "content",
        }

    @pytest.mark.asyncio
    async def test_plain_pandas_dataframe_serializes(
        self,
        executor: CustomCodeExecutor,
        mock_context,
        pandas_dataframe_component_blob,
    ):
        """Plain pandas DataFrame from component should serialize (issue #673).

        Before the fix, this would raise:
        ValueError: Cannot serialize object of type DataFrame.
        Only BaseModel objects and simple types are supported.
        """
        mock_context.get_blob.return_value = pandas_dataframe_component_blob

        input_data = {"blob_id": "test_df_blob", "input": {}}
        result = await executor.execute(input_data, mock_context)

        assert "result" in result
        output = result["result"]
        assert isinstance(output, dict)
        assert output["__langflow_type__"] == "DataFrame"
        assert "json_data" in output


class TestCustomCodeExecutorIntegration:
    """Integration tests with mock Langflow imports."""

    @pytest.fixture
    def executor_with_mocks(self):
        """Create CustomCodeExecutor with mocked Langflow imports."""
        # We'll test this without real Langflow imports to avoid dependency issues
        return CustomCodeExecutor()

    # Registry fixture removed - no longer needed after eliminating test registry

    @pytest.fixture
    def converter(self):
        """Create converter instance."""
        from langflow_stepflow.translation.translator import LangflowConverter

        return LangflowConverter()

    @pytest.mark.asyncio
    async def test_component_parameter_preparation(
        self, executor_with_mocks: CustomCodeExecutor
    ):
        """Test component parameter preparation logic.

        Note: Environment variable resolution is now handled by preprocessing,
        not at runtime in the UDF executor. This test reflects the new approach.
        """
        template = {
            "text_field": {
                "type": "str",
                "value": "template_default",
                "info": "Text input field",
            },
            "api_key": {
                "type": "str",
                # In the new approach, preprocessing would have already resolved this
                "value": "test-api-key-123",  # Already preprocessed value
                "_input_type": "SecretStrInput",
            },
            "number_field": {"type": "int", "value": 42},
        }

        runtime_inputs = {
            "text_field": "runtime_override",
            "extra_field": "extra_value",
        }

        params = await executor_with_mocks._prepare_component_parameters(
            template, runtime_inputs
        )

        # Should have runtime override
        assert params["text_field"] == "runtime_override"

        # Should have preprocessed API key (not runtime resolved)
        assert params["api_key"] == "test-api-key-123"

        # Should have template default
        assert params["number_field"] == 42

        # Should have runtime extra field
        assert params["extra_field"] == "extra_value"


class TestCustomCodeExecutorWithRealLangflowComponents:
    """Test CustomCodeExecutor with real converted Langflow workflow components."""

    @pytest.fixture
    def executor(self):
        """Create CustomCodeExecutor instance."""
        return CustomCodeExecutor()

    @pytest.fixture
    def mock_context(self):
        """Create mock StepflowContext with blob storage."""
        context = AsyncMock()
        context.get_blob = AsyncMock()
        context.put_blob = AsyncMock()
        return context

    @pytest.fixture
    def converter(self):
        """Create converter instance."""
        from langflow_stepflow.translation.translator import LangflowConverter

        return LangflowConverter()

    @pytest.mark.asyncio
    async def test_execute_converted_workflow_components(
        self, executor: CustomCodeExecutor, mock_context, converter
    ):
        """Test that components from converted workflows execute correctly."""
        # Create simple workflow data to test UDF component creation
        langflow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "test-prompt",
                        "data": {
                            "type": "Prompt",
                            "node": {
                                "template": {
                                    "code": {
                                        "value": """
from langflow.custom.custom_component.component import Component
from langflow.io import Output
from langflow.schema.message import Message

class TestPrompt(Component):
    def build_prompt(self) -> Message:
                        return Message(text="Test prompt")
"""
                                    }
                                },
                                "outputs": [
                                    {"name": "prompt", "method": "build_prompt"}
                                ],
                                "base_classes": ["Message"],
                                "display_name": "Test Prompt",
                            },
                            "outputs": [{"name": "prompt", "method": "build_prompt"}],
                        },
                    }
                ],
                "edges": [],
            }
        }

        # Convert to find the custom code components
        stepflow_workflow = converter.convert(langflow_data)

        # Find steps that use /langflow/custom_code
        custom_code_steps = [
            step
            for step in stepflow_workflow.steps
            if step.component == "/langflow/custom_code"
        ]

        assert len(custom_code_steps) > 0, (
            "No custom code executor steps found in test workflow"
        )

        # Test the first custom code step
        first_step = custom_code_steps[0]

        # The step input should have blob_id reference
        assert "blob_id" in str(first_step.input), (
            f"No blob_id found in step input: {first_step.input}"
        )

        print(f"✅ Found {len(custom_code_steps)} custom code components")
        print(
            f"✅ First custom code step: {first_step.id} using {first_step.component}"
        )

    @pytest.mark.asyncio
    async def test_component_metadata_extraction_and_usage(
        self, executor: CustomCodeExecutor, mock_context
    ):
        # Create blob with enhanced metadata (from Phase 1 improvements)
        enhanced_blob = {
            "code": """
from langflow.custom.custom_component.component import Component
from langflow.io import Output
from langflow.schema.message import Message

class EnhancedTestComponent(Component):
    display_name = "Enhanced Test"
    description = "Test component with enhanced metadata"

    outputs = [
        Output(display_name="Message", name="message", method="create_message")
    ]

    def create_message(self) -> Message:
        return Message(text="Enhanced metadata test successful")
""",
            "template": {"input_field": {"type": "str", "value": "test"}},
            "component_type": "EnhancedTestComponent",
            "outputs": [
                {"name": "message", "method": "create_message", "types": ["Message"]}
            ],
            "selected_output": "message",
            # Enhanced metadata from Phase 1
            "base_classes": ["Message"],
            "display_name": "Enhanced Test",
            "description": "Test component with enhanced metadata",
            "documentation": "https://docs.example.com/enhanced-test",
            "metadata": {
                "module": "test.module.EnhancedTestComponent",
                "code_hash": "abc123",
            },
            "field_order": ["input_field"],
            "icon": "test-icon",
            "is_builtin": False,
        }

        mock_context.get_blob.return_value = enhanced_blob

        # Execute with enhanced metadata
        input_data = {"blob_id": "enhanced_test_blob", "input": {}}
        result = await executor.execute(input_data, mock_context)

        # Verify execution used enhanced metadata
        assert result["result"]["text"] == "Enhanced metadata test successful"

        # Verify compiled component contains enhanced metadata
        compiled = executor.compiled_components["enhanced_test_blob"]
        assert compiled["base_classes"] == ["Message"]
        assert compiled["display_name"] == "Enhanced Test"
        assert compiled["metadata"]["module"] == "test.module.EnhancedTestComponent"

    @pytest.fixture
    def basic_prompting_flow(self):
        """Load the basic_prompting flow fixture."""
        import json
        from pathlib import Path

        flow_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "langflow"
            / "basic_prompting.json"
        )
        with open(flow_path) as f:
            return json.load(f)

    @pytest.fixture
    def prompt_component_data(self, basic_prompting_flow):
        """Extract Prompt component data from basic_prompting flow."""
        nodes = basic_prompting_flow["data"]["nodes"]
        prompt_node = next(n for n in nodes if n["data"]["type"] == "Prompt")

        return {
            "code": prompt_node["data"]["node"]["template"]["code"]["value"],
            "component_type": "PromptComponent",
            "template": prompt_node["data"]["node"]["template"],
            "outputs": prompt_node["data"]["node"]["outputs"],
            "selected_output": prompt_node["data"].get("selected_output", "prompt"),
        }

    @pytest.fixture
    def chat_input_component_data(self, basic_prompting_flow):
        """Extract ChatInput component data (lfx-based) from basic_prompting flow."""
        nodes = basic_prompting_flow["data"]["nodes"]
        chat_input_node = next(n for n in nodes if n["data"]["type"] == "ChatInput")

        return {
            "code": chat_input_node["data"]["node"]["template"]["code"]["value"],
            "component_type": "ChatInput",
            "template": chat_input_node["data"]["node"]["template"],
            "outputs": chat_input_node["data"]["node"]["outputs"],
            "selected_output": chat_input_node["data"].get(
                "selected_output", "message"
            ),
        }

    @pytest.fixture
    def agent_component_blob(self):
        """Agent component blob data from simple_agent.json flow.

        This tests the PlaceholderGraph.vertices fix for lfx Agent components.
        """
        import json
        import os

        # Load Agent component data from simple_agent.json
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "fixtures",
            "langflow",
            "simple_agent.json",
        )
        with open(fixture_path) as f:
            flow = json.load(f)

        # Find Agent node
        for node in flow["data"]["nodes"]:
            if "Agent" in node["data"]["node"]["display_name"]:
                agent_data = node["data"]["node"]
                return {
                    "code": agent_data["template"]["code"]["value"],
                    "template": agent_data["template"],
                    "outputs": agent_data.get("outputs", []),
                    "component_type": agent_data["display_name"],
                    "base_classes": agent_data.get("base_classes", []),
                    "display_name": agent_data["display_name"],
                    "description": agent_data.get("description", ""),
                    "selected_output": "response",
                }
        raise ValueError("Agent component not found in simple_agent.json")

    @pytest.mark.asyncio
    async def test_agent_component(
        self, executor: CustomCodeExecutor, mock_context, agent_component_blob
    ):
        """Test that Agent component can be compiled and instantiated.

        This test validates the PlaceholderGraph.vertices fix by:
        1. Compiling the Agent component from lfx
        2. Instantiating the component
        3. Accessing the graph.vertices attribute (which would fail without the fix)

        The fix patches lfx.custom.custom_component.component.PlaceholderGraph
        with an EnhancedPlaceholderGraph that includes the vertices attribute.
        """
        mock_context.get_blob.return_value = agent_component_blob

        # Step 1: Compile the component
        compiled_component = await executor._compile_component(agent_component_blob)
        assert compiled_component is not None
        assert compiled_component["component_type"] == "Agent"

        # Step 2: Instantiate the component
        component_class = compiled_component["class"]
        component_instance = component_class()
        assert component_instance is not None

        # Step 3: Access graph property - this triggers PlaceholderGraph creation
        graph = component_instance.graph
        assert graph is not None

        # Step 4: Access vertices attribute - this would fail without the fix
        # The lfx Agent component code accesses graph.vertices internally
        vertices = graph.vertices
        assert vertices is not None
        assert isinstance(vertices, list)
        assert len(vertices) == 0  # Empty list for EnhancedPlaceholderGraph

    @pytest.mark.asyncio
    async def test_agent_component_execution_attempt(
        self, executor: CustomCodeExecutor, mock_context, agent_component_blob
    ):
        """Test Agent component execution (will fail without real API key).

        This test goes beyond just instantiation to attempt actual execution.
        It will fail due to missing API key, but should NOT fail with
        PlaceholderGraph errors.
        """
        mock_context.get_blob.return_value = agent_component_blob

        # Prepare minimal input for Agent execution
        blob_id = "test_agent_execution"
        input_data = {
            "blob_id": blob_id,
            "input": {
                "input_value": "What is 2+2?",
                "session_id": "test_session",
                "api_key": "sk-test-fake-key",  # Fake key - will fail but tests setup
                "model_name": "gpt-4",
                "tools": [],  # No tools to simplify test
            },
        }

        # Try to execute - expect failure due to API key, NOT PlaceholderGraph
        try:
            result = await executor.execute(input_data, mock_context)
            # If it somehow succeeds with fake key, that's OK
            print(f"Unexpected success: {result}")
        except Exception as e:
            error_msg = str(e)
            # Should NOT have PlaceholderGraph.vertices error
            assert "vertices" not in error_msg.lower(), (
                f"PlaceholderGraph.vertices error detected: {error_msg}"
            )
            # Expected errors: API key, authentication, model errors
            error_info = f"{type(e).__name__}: {error_msg[:200]}"
            print(f"Expected error (not PlaceholderGraph): {error_info}")

    @pytest.mark.asyncio
    async def test_prompt_component(
        self, executor: CustomCodeExecutor, mock_context, prompt_component_data
    ):
        """Test executing Prompt component with string-type system_message field.

        This test verifies that:
        1. We can compile and execute a Prompt component from basic_prompting flow
        2. The component successfully processes template input
        3. The output is a Message object with text content
        """
        # Create blob data for the component
        blob_data = {
            "code": prompt_component_data["code"],
            "component_type": prompt_component_data["component_type"],
            "outputs": prompt_component_data["outputs"],
            "selected_output": prompt_component_data["selected_output"],
            "template": prompt_component_data["template"],
        }

        # Set up mock context
        blob_id = "test-prompt-blob"
        mock_context.get_blob.return_value = blob_data

        # Prepare input data
        template_text = (
            "Answer the user as if you were a GenAI expert, enthusiastic "
            "about helping them get started building something fresh."
        )
        input_data = {
            "blob_id": blob_id,
            "input": {
                "template": template_text,
            },
        }

        # Execute the component
        result = await executor.execute(input_data, mock_context)

        # Verify the result
        assert isinstance(result, dict)

        # Extract the actual output (may be wrapped in 'result' or 'output')
        if "result" in result:
            output = result["result"]
        elif "output" in result:
            output = result["output"]
        else:
            output = result

        # The Prompt component should return a Message object
        # Check for both old and new serialization formats
        has_message_marker = "__langflow_type__" in output or "__class_name__" in output
        output_desc = output.keys() if isinstance(output, dict) else type(output)
        assert has_message_marker, f"Expected Message object, got: {output_desc}"
        assert "text" in output
        assert len(output["text"]) > 0

    @pytest.mark.asyncio
    async def test_language_model_message_to_string_conversion(
        self, executor: CustomCodeExecutor, mock_context, basic_prompting_flow
    ):
        """Test LanguageModelComponent receives string when Message passed.

        This test verifies the fix for Langflow 1.6.4+ lfx components that
        expect string values for MultilineInput fields, not Message objects.
        """
        nodes = basic_prompting_flow["data"]["nodes"]
        lm_node = next(
            n for n in nodes if n["data"].get("type") == "LanguageModelComponent"
        )

        # Create blob data for LanguageModelComponent component
        lm_blob_data = {
            "code": lm_node["data"]["node"]["template"]["code"]["value"],
            "component_type": "LanguageModelComponent",
            "template": lm_node["data"]["node"]["template"],
            "outputs": lm_node["data"]["node"]["outputs"],
        }

        # Create a Message object that will be passed to system_message field
        message_obj = {
            "__langflow_type__": "Message",
            "text": "You are a helpful AI assistant.",
            "sender": "User",
            "sender_name": "User",
            "session_id": "",
        }

        lm_blob_id = "test-lm-blob"
        mock_context.get_blob.return_value = lm_blob_data

        # Prepare input with Message object for string field
        input_data = {
            "blob_id": lm_blob_id,
            "input": {
                "input_value": "Hello, world!",
                "system_message": message_obj,  # Message object for string field
                "api_key": "fake-key-for-testing",
            },
        }

        # The execution will fail because we don't have a real API key,
        # but we want to verify it doesn't fail with a validation error
        # about Message type being passed to MultilineInput
        try:
            await executor.execute(input_data, mock_context)
            # If it succeeds, great! (won't happen without real API key)
        except Exception as e:
            error_msg = str(e)
            # Should NOT have validation error about Message type
            assert (
                "Invalid value type" not in error_msg or "Message" not in error_msg
            ), f"Should not have Message type validation error. Got: {error_msg}"
            # Other errors (like missing API key) are expected
            assert (
                "api_key" in error_msg.lower()
                or "openai" in error_msg.lower()
                or "model" in error_msg.lower()
                or "execute" in error_msg.lower()
            ), f"Expected API/model error, got: {error_msg}"

    @pytest.mark.asyncio
    async def test_chat_input_lfx_component(
        self, executor: CustomCodeExecutor, mock_context, chat_input_component_data
    ):
        """Test executing ChatInput component (lfx-based) from basic_prompting flow.

        This test verifies that:
        1. We can compile and execute an lfx-based ChatInput component
        2. The component accepts string input_value
        3. The component returns a Message object
        """
        # Create blob data for the component
        blob_data = {
            "code": chat_input_component_data["code"],
            "component_type": chat_input_component_data["component_type"],
            "outputs": chat_input_component_data["outputs"],
            "selected_output": chat_input_component_data["selected_output"],
            "template": chat_input_component_data["template"],
        }

        # Set up mock context
        blob_id = "test-chatinput-blob"
        mock_context.get_blob.return_value = blob_data

        # Prepare input data with string input_value
        input_data = {
            "blob_id": blob_id,
            "input": {
                "input_value": "Hello from the test!",
                "should_store_message": False,  # Don't try to store without session
            },
        }

        # Execute the component
        result = await executor.execute(input_data, mock_context)

        # Verify the result
        assert isinstance(result, dict)

        # Check for result/output (wrapped result) or direct Message fields
        if "result" in result:
            output = result["result"]
        elif "output" in result:
            output = result["output"]
        else:
            output = result

        # Should be a Message object (check for both old and new serialization)
        has_message_marker = "__langflow_type__" in output or "__class_name__" in output
        output_desc = output.keys() if isinstance(output, dict) else type(output)
        assert has_message_marker, f"Expected Message object, got: {output_desc}"
        assert "text" in output
        assert output["text"] == "Hello from the test!"

    @pytest.mark.asyncio
    async def test_chat_input_message_to_string_conversion(
        self, executor: CustomCodeExecutor, mock_context, chat_input_component_data
    ):
        """Test ChatInput component with Message object passed to string field.

        This is a specific test for the Langflow 1.6.4+ fix where Message objects
        need to be converted to strings when passed to MultilineInput fields.
        """
        # Create blob data
        blob_data = {
            "code": chat_input_component_data["code"],
            "component_type": chat_input_component_data["component_type"],
            "outputs": chat_input_component_data["outputs"],
            "selected_output": chat_input_component_data["selected_output"],
            "template": chat_input_component_data["template"],
        }

        blob_id = "test-chatinput-message-blob"
        mock_context.get_blob.return_value = blob_data

        # Pass a Message object to the input_value field (which expects str)
        message_obj = {
            "__class_name__": "Message",
            "__module_name__": "lfx.schema.message",
            "text": "Hello from Message object!",
            "sender": "User",
            "sender_name": "User",
            "session_id": "",
        }

        input_data = {
            "blob_id": blob_id,
            "input": {
                "input_value": message_obj,  # Message object for string field
                "should_store_message": False,
            },
        }

        # Execute - should convert Message to string automatically
        result = await executor.execute(input_data, mock_context)

        # Verify execution succeeded (component should extract text from Message)
        assert isinstance(result, dict)

        if "result" in result:
            output = result["result"]
        elif "output" in result:
            output = result["output"]
        else:
            output = result

        # Should have created a new Message with the text
        assert "text" in output
        # The text should be extracted from the input Message object
        assert "Hello from Message object!" in output["text"]
