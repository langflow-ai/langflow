import pytest
from langflow.components.inputs import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.graph.graph.base import Graph
from langflow.graph.graph.constants import Finish
from langflow.graph.state.model import create_state_model
from langflow.template.field.base import UNDEFINED
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
        StateModel = create_state_model(method_one=chat_input_component.message_response)

        state_instance = StateModel()
        assert state_instance.method_one is UNDEFINED
        chat_input_component.set_output_value("message", "test")
        assert state_instance.method_one == "test"

    def test_create_model_and_assign_values_fails(self, chat_input_component):
        StateModel = create_state_model(method_one=chat_input_component.message_response)

        state_instance = StateModel()
        state_instance.method_one = "test"
        assert state_instance.method_one == "test"

    def test_create_with_multiple_components(self, chat_input_component, chat_output_component):
        NewStateModel = create_state_model(
            model_name="NewStateModel",
            first_method=chat_input_component.message_response,
            second_method=chat_output_component.message_response,
        )
        state_instance = NewStateModel()
        assert state_instance.first_method is UNDEFINED
        assert state_instance.second_method is UNDEFINED
        state_instance.first_method = "test"
        state_instance.second_method = 123
        assert state_instance.first_method == "test"
        assert state_instance.second_method == 123

    def test_create_with_pydantic_field(self, chat_input_component):
        StateModel = create_state_model(method_one=chat_input_component.message_response, my_attribute=Field(None))

        state_instance = StateModel()
        state_instance.method_one = "test"
        state_instance.my_attribute = "test"
        assert state_instance.method_one == "test"
        assert state_instance.my_attribute == "test"
        # my_attribute should be of type Any
        state_instance.my_attribute = 123
        assert state_instance.my_attribute == 123

    # Creates a model with fields based on provided keyword arguments
    def test_create_model_with_fields_from_kwargs(self):
        StateModel = create_state_model(field_one=(str, "default"), field_two=(int, 123))
        state_instance = StateModel()
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
        StateModel = create_state_model()
        state_instance = StateModel()
        assert state_instance is not None

    # Ensures model name defaults to "State" if not provided
    def test_default_model_name_to_state(self):
        StateModel = create_state_model()
        assert StateModel.__name__ == "State"
        OtherNameModel = create_state_model(model_name="OtherName")
        assert OtherNameModel.__name__ == "OtherName"

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

    def test_graph_functional_start_state_update(self):
        chat_input = ChatInput(_id="chat_input")
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)
        ChatStateModel = create_state_model(model_name="ChatState", message=chat_output.message_response)
        chat_state_model = ChatStateModel()
        assert chat_state_model.__class__.__name__ == "ChatState"
        assert chat_state_model.message is UNDEFINED

        graph = Graph(chat_input, chat_output)
        graph.prepare()
        # Now iterate through the graph
        # and check that the graph is running
        # correctly
        ids = ["chat_input", "chat_output"]
        results = []
        for result in graph.start():
            results.append(result)

        assert len(results) == 3
        assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
        assert results[-1] == Finish()

        assert chat_state_model.__class__.__name__ == "ChatState"
        assert chat_state_model.message.get_text() == "test"
