import pytest
from pydantic import ValidationError

from langflow.inputs.inputs import MessageTextInput, StrInput, TableInput, _instantiate_input
from langflow.schema.message import Message


@pytest.fixture
def client():
    pass


def test_table_input_valid():
    # Test with a valid list of dictionaries
    data = TableInput(value=[{"key": "value"}, {"key2": "value2"}])
    assert data.value == [{"key": "value"}, {"key2": "value2"}]


def test_table_input_invalid():
    with pytest.raises(ValidationError):
        # Test with an invalid value
        TableInput(value="invalid")

    with pytest.raises(ValidationError):
        # Test with a list containing invalid item
        TableInput(value=[{"key": "value"}, "invalid"])


def test_str_input_valid():
    data = StrInput(value="This is a string")
    assert data.value == "This is a string"


def test_str_input_invalid():
    with pytest.warns(UserWarning):
        # Test with an invalid value
        StrInput(value=1234)


def test_message_text_input_valid():
    # Test with a valid string
    data = MessageTextInput(value="This is a message")
    assert data.value == "This is a message"

    # Test with a valid Message object
    msg = Message(text="This is a message")
    data = MessageTextInput(value=msg)
    assert data.value == "This is a message"


def test_message_text_input_invalid():
    with pytest.raises(ValidationError):
        # Test with an invalid value
        MessageTextInput(value=1234)


def test_instantiate_input_valid():
    data = {"value": "This is a string"}
    input_instance = _instantiate_input("StrInput", data)
    assert isinstance(input_instance, StrInput)
    assert input_instance.value == "This is a string"


def test_instantiate_input_invalid():
    with pytest.raises(ValueError):
        # Test with an invalid input type
        _instantiate_input("InvalidInput", {"value": "This is a string"})
