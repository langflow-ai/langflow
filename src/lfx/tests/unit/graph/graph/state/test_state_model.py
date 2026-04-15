# ruff: noqa: FBT001
import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish
from lfx.graph.state.model import create_state_model
from lfx.io import HandleInput, Output
from lfx.schema.message import Message
from lfx.template.field.base import UNDEFINED
from pydantic import Field


@pytest.fixture
def chat_input_component():
    return ChatInput()


@pytest.fixture
def chat_output_component():
    return ChatOutput()


class TestCreateStateModel:
    # Successfully create a model with valid method return type annotations

    def test_create_model_with_valid_return_type_annotations(self, chat_input_component):
        state_model = create_state_model(method_one=chat_input_component.message_response)

        state_instance = state_model()
        assert state_instance.method_one is UNDEFINED
        chat_input_component.set_output_value("message", "test")
        assert state_instance.method_one == "test"

    def test_create_model_and_assign_values_fails(self, chat_input_component):
        state_model = create_state_model(method_one=chat_input_component.message_response)

        state_instance = state_model()
        state_instance.method_one = "test"
        assert state_instance.method_one == "test"

    def test_create_with_multiple_components(self, chat_input_component, chat_output_component):
        new_state_model = create_state_model(
            model_name="NewStateModel",
            first_method=chat_input_component.message_response,
            second_method=chat_output_component.message_response,
        )
        state_instance = new_state_model()
        assert state_instance.first_method is UNDEFINED
        assert state_instance.second_method is UNDEFINED
        state_instance.first_method = "test"
        state_instance.second_method = 123
        assert state_instance.first_method == "test"
        assert state_instance.second_method == 123

    def test_create_with_pydantic_field(self, chat_input_component):
        state_model = create_state_model(method_one=chat_input_component.message_response, my_attribute=Field(None))

        state_instance = state_model()
        state_instance.method_one = "test"
        state_instance.my_attribute = "test"
        assert state_instance.method_one == "test"
        assert state_instance.my_attribute == "test"
        # my_attribute should be of type Any
        state_instance.my_attribute = 123
        assert state_instance.my_attribute == 123

    # Creates a model with fields based on provided keyword arguments
    def test_create_model_with_fields_from_kwargs(self):
        state_model = create_state_model(field_one=(str, "default"), field_two=(int, 123))
        state_instance = state_model()
        assert state_instance.field_one == "default"
        assert state_instance.field_two == 123

    # Raises ValueError for invalid field type in tuple-based definitions
    def test_raise_typeerror_for_invalid_field_type_in_tuple(self):
        with pytest.raises(TypeError, match="Invalid type for field invalid_field"):
            create_state_model(invalid_field=("not_a_type", "default"))

    # Raises ValueError for unsupported value types in keyword arguments
    def test_raise_valueerror_for_unsupported_value_types(self):
        with pytest.raises(ValueError, match="Invalid value type <class 'int'> for field invalid_field"):
            create_state_model(invalid_field=123)

    # Handles empty keyword arguments gracefully
    def test_handle_empty_kwargs_gracefully(self):
        state_model = create_state_model()
        state_instance = state_model()
        assert state_instance is not None

    # Ensures model name defaults to "State" if not provided
    def test_default_model_name_to_state(self):
        state_model = create_state_model()
        assert state_model.__name__ == "State"
        other_name_model = create_state_model(model_name="OtherName")
        assert other_name_model.__name__ == "OtherName"

    # Validates that callable values are properly type-annotated

    def test_create_model_with_invalid_callable(self):
        class MockComponent:
            def method_one(self) -> str:
                return "test"

            def method_two(self) -> int:
                return 123

        mock_component = MockComponent()
        with pytest.raises(ValueError, match="get_output_by_method"):
            create_state_model(method_one=mock_component.method_one, method_two=mock_component.method_two)

    @pytest.mark.asyncio
    async def test_graph_functional_start_state_update(self):
        chat_input = ChatInput(_id="chat_input", session_id="test", input_value="test")
        chat_output = ChatOutput(input_value="test", _id="chat_output", session_id="test")
        chat_output.set(sender_name=chat_input.message_response)
        chat_state_model = create_state_model(model_name="ChatState", message=chat_output.message_response)()
        assert chat_state_model.__class__.__name__ == "ChatState"
        assert chat_state_model.message is UNDEFINED

        graph = Graph(chat_input, chat_output)
        graph.prepare()
        # Now iterate through the graph
        # and check that the graph is running
        # correctly
        ids = ["chat_input", "chat_output"]
        results = [result async for result in graph.async_start()]

        assert len(results) == 3
        assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
        assert results[-1] == Finish()

        assert chat_state_model.__class__.__name__ == "ChatState"
        assert hasattr(chat_state_model.message, "get_text")
        assert chat_state_model.message.get_text() == "test"

    @pytest.mark.asyncio
    async def test_state_model_with_group_outputs_conditional_routing(self):
        """Test that create_state_model works with components that have group_outputs=True.

        Components with conditional routing (like AgentStep) have multiple outputs with
        group_outputs=True. These outputs should always be processed even if not connected,
        so the routing logic can execute and decide which branch to take.
        """

        class ConditionalRouterComponent(Component):
            """A simple conditional router for testing."""

            display_name = "Conditional Router"

            inputs = [
                HandleInput(name="input_value", display_name="Input", input_types=["Message"]),
            ]
            outputs = [
                Output(
                    display_name="Output A",
                    name="output_a",
                    method="get_output_a",
                    group_outputs=True,
                ),
                Output(
                    display_name="Output B",
                    name="output_b",
                    method="get_output_b",
                    group_outputs=True,
                ),
            ]

            def __init__(self, _id: str | None = None):
                super().__init__(_id=_id)
                self._route_to_a = True

            def set_route(self, route_to_a: bool):
                self._route_to_a = route_to_a

            def get_output_a(self) -> Message:
                if not self._route_to_a:
                    self.stop("output_a")
                    return Message(text="")
                self.stop("output_b")
                return Message(text="Routed to A")

            def get_output_b(self) -> Message:
                if self._route_to_a:
                    self.stop("output_b")
                    return Message(text="")
                self.stop("output_a")
                return Message(text="Routed to B")

        class ReceiverComponent(Component):
            """A simple receiver component."""

            display_name = "Receiver"

            inputs = [
                HandleInput(name="input_value", display_name="Input", input_types=["Message"]),
            ]
            outputs = [
                Output(display_name="Output", name="output", method="get_output"),
            ]

            def get_output(self) -> Message:
                return self.input_value

        # Create components
        router = ConditionalRouterComponent(_id="router")
        receiver = ReceiverComponent(_id="receiver")

        # Connect only output_b to receiver (output_a is NOT connected but has group_outputs=True)
        receiver.set(input_value=router.get_output_b)

        # Create state model to capture output_a (which is NOT connected to anything)
        state_model = create_state_model(
            model_name="RouterState",
            output_a=router.get_output_a,
        )()

        assert state_model.output_a is UNDEFINED

        # Build graph from router to receiver (output_b is connected)
        graph = Graph(router, receiver)
        graph.prepare()

        # Set routing to A - output_a should fire even though it's not connected
        router.set_route(route_to_a=True)

        # Run the graph
        results = [result async for result in graph.async_start()]
        assert results[-1] == Finish()

        # The key assertion: output_a should have been processed and have a value
        # even though it's not connected to anything in the graph
        assert state_model.output_a is not UNDEFINED
        assert isinstance(state_model.output_a, Message)
        assert state_model.output_a.text == "Routed to A"
