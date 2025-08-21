"""Base classes for integration testing."""

import uuid
from abc import abstractmethod
from typing import Any, ClassVar

from langflow.custom import Component
from langflow.graph import Graph
from langflow.schema.data import Data
from langflow.schema.message import Message

from .assertions import AssertionHelpers
from .fixtures import TestDataFactory
from .runners import ComponentRunner, FlowRunner


class IntegrationTestCase:
    """Base class for all integration tests with common utilities."""

    def setup_method(self):
        """Setup method called before each test method."""
        self.session_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        self.assertions = AssertionHelpers()
        self.test_data = TestDataFactory()

    def teardown_method(self):
        """Teardown method called after each test method."""


class ComponentTest(IntegrationTestCase):
    """Base class for testing individual components.

    Example:
        class TestChatInput(ComponentTest):
            component_class = ChatInput

            def test_basic_functionality(self):
                result = self.run_component(input_text="Hello")
                self.assert_message_output(result, "Hello")
    """

    # Subclasses must set this
    component_class: ClassVar[type[Component] | None] = None

    # Optional configuration
    default_inputs: ClassVar[dict[str, Any]] = {}
    required_env_vars: ClassVar[list[str]] = []
    requires_api_key: ClassVar[bool] = False

    def setup_method(self):
        """Setup method called before each test method."""
        super().setup_method()
        if self.component_class is None:
            msg = f"{self.__class__.__name__} must set component_class"
            raise ValueError(msg)

        self.runner = ComponentRunner()
        self._component_instance = None

    @property
    def component_instance(self) -> Component:
        """Get or create component instance with default inputs."""
        if self._component_instance is None:
            inputs = {**self.default_inputs}
            inputs.setdefault("_user_id", self.user_id)
            self._component_instance = self.component_class(**inputs)
        return self._component_instance

    async def run_component(
        self, inputs: dict[str, Any] | None = None, run_input: Any = None, session_id: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Run the component with given inputs.

        Args:
            inputs: Component input parameters
            run_input: Input value to pass to the component
            session_id: Session ID for the run
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of component outputs
        """
        merged_inputs = {**self.default_inputs, **(inputs or {})}

        return await self.runner.run_single_component(
            self.component_class,
            inputs=merged_inputs,
            run_input=run_input,
            session_id=session_id or self.session_id,
            **kwargs,
        )

    def assert_output_type(self, outputs: dict[str, Any], output_name: str, expected_type: type):
        """Assert that an output has the expected type."""
        assert output_name in outputs, f"Output '{output_name}' not found in {list(outputs.keys())}"
        actual_value = outputs[output_name]
        assert isinstance(actual_value, expected_type), (
            f"Expected {output_name} to be {expected_type.__name__}, got {type(actual_value).__name__}"
        )

    def assert_message_output(self, outputs: dict[str, Any], expected_text: str, output_name: str = "message"):
        """Assert message output with expected text."""
        self.assert_output_type(outputs, output_name, Message)
        message = outputs[output_name]
        assert message.text == expected_text, f"Expected '{expected_text}', got '{message.text}'"

    def assert_data_output(self, outputs: dict[str, Any], expected_data: Any, output_name: str = "data"):
        """Assert data output with expected content."""
        self.assert_output_type(outputs, output_name, Data)
        data = outputs[output_name]
        assert data.data == expected_data, f"Expected {expected_data}, got {data.data}"


class FlowTest(IntegrationTestCase):
    """Base class for testing complete flows.

    Example:
        class TestChatFlow(FlowTest):
            def build_flow(self) -> Graph:
                graph = Graph()
                input_comp = graph.add_component(ChatInput())
                output_comp = graph.add_component(ChatOutput())
                graph.add_component_edge(input_comp, ("message", "input_value"), output_comp)
                return graph

            def test_flow_execution(self):
                result = self.run_flow(run_input="Hello")
                self.assert_message_in_outputs(result, "Hello")
    """

    def setup_method(self):
        """Setup method called before each test method."""
        super().setup_method()
        self.runner = FlowRunner()
        self._graph = None

    @abstractmethod
    def build_flow(self) -> Graph:
        """Build and return the flow graph. Must be implemented by subclasses."""

    @property
    def graph(self) -> Graph:
        """Get or build the flow graph."""
        if self._graph is None:
            self._graph = self.build_flow()
        return self._graph

    async def run_flow(self, run_input: Any = None, session_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Run the complete flow.

        Args:
            run_input: Input to pass to the flow
            session_id: Session ID for the run
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of flow outputs
        """
        return await self.runner.run_flow(
            self.graph, run_input=run_input, session_id=session_id or self.session_id, **kwargs
        )

    def assert_message_in_outputs(self, outputs: dict[str, Any], expected_text: str):
        """Assert that outputs contain a message with expected text."""
        messages = [v for v in outputs.values() if isinstance(v, Message)]
        assert messages, f"No Message outputs found in {list(outputs.keys())}"

        for message in messages:
            if message.text == expected_text:
                return

        message_texts = [m.text for m in messages]
        msg = f"Expected message '{expected_text}' not found. Available: {message_texts}"
        raise AssertionError(msg)


class APITest(IntegrationTestCase):
    """Base class for API integration tests.

    Example:
        class TestFlowAPI(APITest):
            async def test_create_flow(self):
                flow_data = self.test_data.create_flow_data()
                response = await self.post("/api/v1/flows/", json=flow_data)
                self.assert_success_response(response)
    """

    def __init__(self):
        super().__init__()
        self._client = None
        self._headers = None

    async def get_client(self):
        """Get HTTP client. Override for custom client setup."""
        # This would be injected via fixtures in actual implementation
        return self._client

    async def get_headers(self):
        """Get authentication headers. Override for custom auth."""
        return self._headers or {}

    async def get(self, url: str, **kwargs):
        """Make GET request."""
        client = await self.get_client()
        headers = await self.get_headers()
        return await client.get(url, headers=headers, **kwargs)

    async def post(self, url: str, **kwargs):
        """Make POST request."""
        client = await self.get_client()
        headers = await self.get_headers()
        return await client.post(url, headers=headers, **kwargs)

    async def put(self, url: str, **kwargs):
        """Make PUT request."""
        client = await self.get_client()
        headers = await self.get_headers()
        return await client.put(url, headers=headers, **kwargs)

    async def delete(self, url: str, **kwargs):
        """Make DELETE request."""
        client = await self.get_client()
        headers = await self.get_headers()
        return await client.delete(url, headers=headers, **kwargs)

    def assert_success_response(self, response, expected_status: int = 200):
        """Assert successful HTTP response."""
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
        )

    def assert_error_response(self, response, expected_status: int = 400):
        """Assert error HTTP response."""
        assert response.status_code == expected_status, (
            f"Expected error status {expected_status}, got {response.status_code}. Response: {response.text}"
        )


def auto_component_test(component_class: type[Component]):
    """Decorator to automatically generate basic tests for a component.

    Example:
        @auto_component_test(ChatInput)
        class TestChatInput(ComponentTest):
            pass  # Basic tests are auto-generated
    """

    def decorator(test_class):
        # Add component_class if not set
        if not hasattr(test_class, "component_class"):
            test_class.component_class = component_class

        # Generate basic test methods if they don't exist
        if not hasattr(test_class, "test_component_initialization"):

            def test_component_initialization(self):
                """Test that component can be initialized."""
                instance = self.component_instance
                assert instance is not None
                assert isinstance(instance, component_class)

            test_class.test_component_initialization = test_component_initialization

        if not hasattr(test_class, "test_component_inputs_outputs"):

            def test_component_inputs_outputs(self):
                """Test that component has expected inputs and outputs."""
                instance = self.component_instance
                assert hasattr(instance, "inputs")
                assert hasattr(instance, "outputs")
                assert len(instance.inputs) >= 0
                assert len(instance.outputs) >= 0

            test_class.test_component_inputs_outputs = test_component_inputs_outputs

        return test_class

    return decorator
