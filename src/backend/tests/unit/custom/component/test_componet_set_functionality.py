import pytest
from langflow.custom import Component
from langflow.inputs.inputs import MessageTextInput, StrInput


@pytest.fixture
def setup_component():
    # Create a sample component for testing
    component = Component()
    # Define inputs for the component
    component.inputs = [
        MessageTextInput(name="list_message_input", is_list=True),  # Input for a mock component
        StrInput(name="mixed_input"),  # Input for a mixed list
    ]
    return component


def test_set_with_mixed_list_input(setup_component):
    component = setup_component
    # Create a mock component to include in the list
    mock_component = Component()
    message_input_1 = "message data1"
    message_input_2 = "message data2"
    data = {"mixed_input": [message_input_1, message_input_2], "list_message_input": [message_input_1, mock_component]}
    component.set(**data)

    # Assert that the mixed input was set correctly
    assert hasattr(component, "mixed_input")
    assert len(component.mixed_input) == 2
    assert component.mixed_input[0] == message_input_1
    assert component.mixed_input[1] == message_input_2
    assert component.list_message_input[0] == message_input_1
    assert component.list_message_input[1] == mock_component


def test_set_with_message_text_input_list(setup_component):
    component = setup_component
    # Create a list of MessageTextInput instances
    message_input_1 = "message data1"
    message_input_2 = "message data2"
    data = {"mixed_input": [message_input_1, message_input_2], "list_message_input": [message_input_1, message_input_2]}
    # Set a list containing MessageTextInput instances
    component.set(**data)

    # Assert that the mixed input was set correctly
    assert hasattr(component, "mixed_input")
    assert len(component.list_message_input) == 2
    assert component.list_message_input[0] == message_input_1
    assert component.list_message_input[1] == message_input_2
