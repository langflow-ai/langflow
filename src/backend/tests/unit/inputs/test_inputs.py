import pytest
from pydantic import ValidationError

from langflow.inputs.inputs import (
    BoolInput,
    CodeInput,
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
)
from langflow.inputs.utils import instantiate_input
from langflow.schema.message import Message


def test_table_input_valid():
    data = TableInput(name="valid_table", value=[{"key": "value"}, {"key2": "value2"}])
    assert data.value == [{"key": "value"}, {"key2": "value2"}]


def test_table_input_invalid():
    with pytest.raises(ValidationError):
        TableInput(name="invalid_table", value="invalid")

    with pytest.raises(ValidationError):
        TableInput(name="invalid_table", value=[{"key": "value"}, "invalid"])


def test_str_input_valid():
    data = StrInput(name="valid_str", value="This is a string")
    assert data.value == "This is a string"


def test_str_input_invalid():
    with pytest.warns(UserWarning):
        StrInput(name="invalid_str", value=1234)


def test_message_text_input_valid():
    data = MessageTextInput(name="valid_msg", value="This is a message")
    assert data.value == "This is a message"

    msg = Message(text="This is a message")
    data = MessageTextInput(name="valid_msg", value=msg)
    assert data.value == "This is a message"


def test_message_text_input_invalid():
    with pytest.raises(ValidationError):
        MessageTextInput(name="invalid_msg", value=1234)


def test_instantiate_input_valid():
    data = {"name": "valid_input", "value": "This is a string"}
    input_instance = instantiate_input("StrInput", data)
    assert isinstance(input_instance, StrInput)
    assert input_instance.value == "This is a string"


def test_instantiate_input_invalid():
    with pytest.raises(ValueError):
        instantiate_input("InvalidInput", {"name": "invalid_input", "value": "This is a string"})


def test_handle_input_valid():
    data = HandleInput(name="valid_handle", input_types=["BaseLanguageModel"])
    assert data.input_types == ["BaseLanguageModel"]


def test_handle_input_invalid():
    with pytest.raises(ValidationError):
        HandleInput(name="invalid_handle", input_types="BaseLanguageModel")


def test_data_input_valid():
    data_input = DataInput(name="valid_data", input_types=["Data"])
    assert data_input.input_types == ["Data"]


def test_prompt_input_valid():
    prompt_input = PromptInput(name="valid_prompt", value="Enter your name")
    assert prompt_input.value == "Enter your name"


def test_code_input_valid():
    code_input = CodeInput(name="valid_code", value="def hello():\n    print('Hello, World!')")
    assert code_input.value == "def hello():\n    print('Hello, World!')"


def test_multiline_input_valid():
    multiline_input = MultilineInput(name="valid_multiline", value="This is a\nmultiline input")
    assert multiline_input.value == "This is a\nmultiline input"
    assert multiline_input.multiline is True


def test_multiline_input_invalid():
    with pytest.raises(ValidationError):
        MultilineInput(name="invalid_multiline", value=1234)


def test_multiline_secret_input_valid():
    multiline_secret_input = MultilineSecretInput(name="valid_multiline_secret", value="secret")
    assert multiline_secret_input.value == "secret"
    assert multiline_secret_input.password is True


def test_multiline_secret_input_invalid():
    with pytest.raises(ValidationError):
        MultilineSecretInput(name="invalid_multiline_secret", value=1234)


def test_secret_str_input_valid():
    secret_str_input = SecretStrInput(name="valid_secret_str", value="supersecret")
    assert secret_str_input.value == "supersecret"
    assert secret_str_input.password is True


def test_secret_str_input_invalid():
    with pytest.raises(ValidationError):
        SecretStrInput(name="invalid_secret_str", value=1234)


def test_int_input_valid():
    int_input = IntInput(name="valid_int", value=10)
    assert int_input.value == 10


def test_int_input_invalid():
    with pytest.raises(ValidationError):
        IntInput(name="invalid_int", value="not_an_int")


def test_float_input_valid():
    float_input = FloatInput(name="valid_float", value=10.5)
    assert float_input.value == 10.5


def test_float_input_invalid():
    with pytest.raises(ValidationError):
        FloatInput(name="invalid_float", value="not_a_float")


def test_bool_input_valid():
    bool_input = BoolInput(name="valid_bool", value=True)
    assert bool_input.value is True


def test_bool_input_invalid():
    with pytest.raises(ValidationError):
        BoolInput(name="invalid_bool", value="not_a_bool")


def test_nested_dict_input_valid():
    nested_dict_input = NestedDictInput(name="valid_nested_dict", value={"key": "value"})
    assert nested_dict_input.value == {"key": "value"}


def test_nested_dict_input_invalid():
    with pytest.raises(ValidationError):
        NestedDictInput(name="invalid_nested_dict", value="not_a_dict")


def test_dict_input_valid():
    dict_input = DictInput(name="valid_dict", value={"key": "value"})
    assert dict_input.value == {"key": "value"}


def test_dict_input_invalid():
    with pytest.raises(ValidationError):
        DictInput(name="invalid_dict", value="not_a_dict")


def test_dropdown_input_valid():
    dropdown_input = DropdownInput(name="valid_dropdown", options=["option1", "option2"])
    assert dropdown_input.options == ["option1", "option2"]


def test_dropdown_input_invalid():
    with pytest.raises(ValidationError):
        DropdownInput(name="invalid_dropdown", options="option1")


def test_multiselect_input_valid():
    multiselect_input = MultiselectInput(name="valid_multiselect", value=["option1", "option2"])
    assert multiselect_input.value == ["option1", "option2"]


def test_multiselect_input_invalid():
    with pytest.raises(ValidationError):
        MultiselectInput(name="invalid_multiselect", value="option1")


def test_file_input_valid():
    file_input = FileInput(name="valid_file", value=["/path/to/file"])
    assert file_input.value == ["/path/to/file"]


def test_instantiate_input_comprehensive():
    valid_data = {
        "StrInput": {"name": "str_input", "value": "A string"},
        "IntInput": {"name": "int_input", "value": 10},
        "FloatInput": {"name": "float_input", "value": 10.5},
        "BoolInput": {"name": "bool_input", "value": True},
        "DictInput": {"name": "dict_input", "value": {"key": "value"}},
        "MultiselectInput": {
            "name": "multiselect_input",
            "value": ["option1", "option2"],
        },
    }

    for input_type, data in valid_data.items():
        input_instance = instantiate_input(input_type, data)
        assert isinstance(input_instance, InputTypesMap[input_type])

    with pytest.raises(ValueError):
        instantiate_input("InvalidInput", {"name": "invalid_input", "value": "Invalid"})
