import pytest
from pydantic import ValidationError

from langflow.inputs.inputs import (
    BoolInput,
    DataInput,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    InputTypesMap,
    IntInput,
    MessageTextInput,
    MultilineInput,
    MultilineSecretInput,
    MultiselectInput,
    NestedDictInput,
    PromptInput,
    SecretStrInput,
    StrInput,
    TableInput,
    _instantiate_input,
)
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


def test_handle_input_valid():
    data = HandleInput(input_types=["BaseLanguageModel"])
    assert data.input_types == ["BaseLanguageModel"]


def test_handle_input_invalid():
    with pytest.raises(ValidationError):
        HandleInput(input_types="BaseLanguageModel")  # should be a list, not a string


def test_data_input_valid():
    data_input = DataInput(input_types=["Data"])
    assert data_input.input_types == ["Data"]


def test_prompt_input_valid():
    prompt_input = PromptInput(value="Enter your name")
    assert prompt_input.value == "Enter your name"


def test_multiline_input_valid():
    multiline_input = MultilineInput(value="This is a\nmultiline input")
    assert multiline_input.value == "This is a\nmultiline input"
    assert multiline_input.multiline is True


def test_multiline_input_invalid():
    with pytest.raises(ValidationError):
        MultilineInput(value=1234)  # should be a string, not an integer


def test_multiline_secret_input_valid():
    multiline_secret_input = MultilineSecretInput(value="secret")
    assert multiline_secret_input.value == "secret"
    assert multiline_secret_input.password is True


def test_multiline_secret_input_invalid():
    with pytest.raises(ValidationError):
        MultilineSecretInput(value=1234)  # should be a string, not an integer


def test_secret_str_input_valid():
    secret_str_input = SecretStrInput(value="supersecret")
    assert secret_str_input.value == "supersecret"
    assert secret_str_input.password is True


def test_secret_str_input_invalid():
    with pytest.raises(ValidationError):
        SecretStrInput(value=1234)  # should be a string, not an integer


def test_int_input_valid():
    int_input = IntInput(value=10)
    assert int_input.value == 10


def test_int_input_invalid():
    with pytest.raises(ValidationError):
        IntInput(value="not_an_int")  # should be an integer, not a string


def test_float_input_valid():
    float_input = FloatInput(value=10.5)
    assert float_input.value == 10.5


def test_float_input_invalid():
    with pytest.raises(ValidationError):
        FloatInput(value="not_a_float")  # should be a float, not a string


def test_bool_input_valid():
    bool_input = BoolInput(value=True)
    assert bool_input.value is True


def test_bool_input_invalid():
    with pytest.raises(ValidationError):
        BoolInput(value="not_a_bool")  # should be a bool, not a string


def test_nested_dict_input_valid():
    nested_dict_input = NestedDictInput(value={"key": "value"})
    assert nested_dict_input.value == {"key": "value"}


def test_nested_dict_input_invalid():
    with pytest.raises(ValidationError):
        NestedDictInput(value="not_a_dict")  # should be a dict, not a string


def test_dict_input_valid():
    dict_input = DictInput(value={"key": "value"})
    assert dict_input.value == {"key": "value"}


def test_dict_input_invalid():
    with pytest.raises(ValidationError):
        DictInput(value="not_a_dict")  # should be a dict, not a string


def test_dropdown_input_valid():
    dropdown_input = DropdownInput(options=["option1", "option2"])
    assert dropdown_input.options == ["option1", "option2"]


def test_dropdown_input_invalid():
    with pytest.raises(ValidationError):
        DropdownInput(options="option1")  # should be a list, not a string


def test_multiselect_input_valid():
    multiselect_input = MultiselectInput(value=["option1", "option2"])
    assert multiselect_input.value == ["option1", "option2"]


def test_multiselect_input_invalid():
    with pytest.raises(ValidationError):
        MultiselectInput(value="option1")  # should be a list, not a string


def test_file_input_valid():
    file_input = FileInput(value=["/path/to/file"])
    assert file_input.value == ["/path/to/file"]


def test_instantiate_input_comprehensive():
    valid_data = {
        "StrInput": {"value": "A string"},
        "IntInput": {"value": 10},
        "FloatInput": {"value": 10.5},
        "BoolInput": {"value": True},
        "DictInput": {"value": {"key": "value"}},
        "MultiselectInput": {"value": ["option1", "option2"]},
    }

    for input_type, data in valid_data.items():
        input_instance = _instantiate_input(input_type, data)
        assert isinstance(input_instance, InputTypesMap[input_type])

    with pytest.raises(ValueError):
        _instantiate_input("InvalidInput", {"value": "Invalid"})  # Invalid input type
