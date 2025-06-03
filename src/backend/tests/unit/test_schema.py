from collections.abc import Sequence as SequenceABC
from types import NoneType
from typing import Union

import pytest
from langflow.inputs.inputs import BoolInput, DictInput, FloatInput, InputTypes, IntInput, MessageTextInput
from langflow.io.schema import schema_to_langflow_inputs
from langflow.schema.data import Data
from langflow.template import Input, Output
from langflow.template.field.base import UNDEFINED
from langflow.type_extraction.type_extraction import post_process_type
from pydantic import BaseModel, Field, ValidationError


class TestInput:
    def test_field_type_str(self):
        input_obj = Input(field_type="str")
        assert input_obj.field_type == "str"

    def test_field_type_type(self):
        input_obj = Input(field_type=int)
        assert input_obj.field_type == "int"

    def test_invalid_field_type(self):
        with pytest.raises(ValidationError):
            Input(field_type=123)

    def test_serialize_field_type(self):
        input_obj = Input(field_type="str")
        assert input_obj.serialize_field_type("str", None) == "str"

    def test_validate_type_string(self):
        input_obj = Input(field_type="str")
        assert input_obj.field_type == "str"

    def test_validate_type_class(self):
        input_obj = Input(field_type=int)
        assert input_obj.field_type == "int"

    def test_post_process_type_function(self):
        # Basic types
        assert set(post_process_type(int)) == {int}
        assert set(post_process_type(float)) == {float}

        # List and Sequence types
        assert set(post_process_type(list[int])) == {int}
        assert set(post_process_type(SequenceABC[float])) == {float}

        # Union types
        assert set(post_process_type(Union[int, str])) == {int, str}  # noqa: UP007
        assert set(post_process_type(Union[int, SequenceABC[str]])) == {int, str}  # noqa: UP007
        assert set(post_process_type(Union[int, SequenceABC[int]])) == {int}  # noqa: UP007

        # Nested Union with lists
        assert set(post_process_type(Union[list[int], list[str]])) == {int, str}  # noqa: UP007
        assert set(post_process_type(Union[int, list[str], list[float]])) == {int, str, float}  # noqa: UP007

        # Custom data types
        assert set(post_process_type(Data)) == {Data}
        assert set(post_process_type(list[Data])) == {Data}

        # Union with custom types
        assert set(post_process_type(Union[Data, str])) == {Data, str}  # noqa: UP007
        assert set(post_process_type(Union[Data, int, list[str]])) == {Data, int, str}  # noqa: UP007

        # Empty lists and edge cases
        assert set(post_process_type(list)) == {list}
        assert set(post_process_type(Union[int, None])) == {int, NoneType}  # noqa: UP007
        assert set(post_process_type(Union[list[None], None])) == {None, NoneType}  # noqa: UP007

        # Handling complex nested structures
        assert set(post_process_type(Union[SequenceABC[int | str], list[float]])) == {int, str, float}  # noqa: UP007
        assert set(post_process_type(Union[int | list[str] | list[float], str])) == {int, str, float}  # noqa: UP007

        # Non-generic types should return as is
        assert set(post_process_type(dict)) == {dict}
        assert set(post_process_type(tuple)) == {tuple}

        # Union with custom types
        assert set(post_process_type(Union[Data, str])) == {Data, str}  # noqa: UP007
        assert set(post_process_type(Data | str)) == {Data, str}
        assert set(post_process_type(Data | int | list[str])) == {Data, int, str}

        # More complex combinations with Data
        assert set(post_process_type(Data | list[float])) == {Data, float}
        assert set(post_process_type(Data | Union[int, str])) == {Data, int, str}  # noqa: UP007
        assert set(post_process_type(Data | list[int] | None)) == {Data, int, type(None)}
        assert set(post_process_type(Data | Union[float, None])) == {Data, float, type(None)}  # noqa: UP007

        # Multiple Data types combined
        assert set(post_process_type(Union[Data, str | float])) == {Data, str, float}  # noqa: UP007
        assert set(post_process_type(Union[Data | float | str, int])) == {Data, int, float, str}  # noqa: UP007

        # Testing with nested unions and lists
        assert set(post_process_type(Union[list[Data], list[int | str]])) == {Data, int, str}  # noqa: UP007
        assert set(post_process_type(Data | list[float | str])) == {Data, float, str}

    def test_input_to_dict(self):
        input_obj = Input(field_type="str")
        assert input_obj.to_dict() == {
            "type": "str",
            "required": False,
            "placeholder": "",
            "list": False,
            "show": True,
            "multiline": False,
            "fileTypes": [],
            "file_path": "",
            "advanced": False,
            "title_case": False,
            "dynamic": False,
            "info": "",
            "input_types": ["Text"],
            "load_from_db": False,
        }


class TestOutput:
    def test_output_default(self):
        output_obj = Output(name="test_output")
        assert output_obj.name == "test_output"
        assert output_obj.value == UNDEFINED
        assert output_obj.cache is True

    def test_output_add_types(self):
        output_obj = Output(name="test_output")
        output_obj.add_types(["str", "int"])
        assert output_obj.types == ["str", "int"]

    def test_output_set_selected(self):
        output_obj = Output(name="test_output", types=["str", "int"])
        output_obj.set_selected()
        assert output_obj.selected == "str"

    def test_output_to_dict(self):
        output_obj = Output(name="test_output")
        assert output_obj.to_dict() == {
            "allows_loop": False,
            "types": [],
            "name": "test_output",
            "display_name": "test_output",
            "group_outputs": False,
            "cache": True,
            "value": "__UNDEFINED__",
            "tool_mode": True,
        }

    def test_output_validate_display_name(self):
        output_obj = Output(name="test_output")
        assert output_obj.display_name == "test_output"

    def test_output_validate_model(self):
        output_obj = Output(name="test_output", value="__UNDEFINED__")
        assert output_obj.validate_model() == output_obj


class TestPostProcessType:
    def test_int_type(self):
        assert post_process_type(int) == [int]

    def test_list_int_type(self):
        assert post_process_type(list[int]) == [int]

    def test_union_type(self):
        assert set(post_process_type(Union[int, str])) == {int, str}  # noqa: UP007

    def test_custom_type(self):
        class CustomType:
            pass

        assert post_process_type(CustomType) == [CustomType]

    def test_list_custom_type(self):
        class CustomType:
            pass

        assert post_process_type(list[CustomType]) == [CustomType]

    def test_union_custom_type(self):
        class CustomType:
            pass

        assert set(post_process_type(Union[CustomType, int])) == {CustomType, int}  # noqa: UP007


def test_schema_to_langflow_inputs():
    # Define a test Pydantic model with various field types
    class TestSchema(BaseModel):
        text_field: str = Field(title="Custom Text Title", description="A text field")
        number_field: int = Field(description="A number field")
        bool_field: bool = Field(description="A boolean field")
        dict_field: dict = Field(description="A dictionary field")
        list_field: list[str] = Field(description="A list of strings")

    # Convert schema to Langflow inputs
    inputs = schema_to_langflow_inputs(TestSchema)

    # Verify the number of inputs matches the schema fields
    assert len(inputs) == 5

    # Helper function to find input by name
    def find_input(name: str) -> InputTypes | None:
        for _input in inputs:
            if _input.name == name:
                return _input
        return None

    # Test text field
    text_input = find_input("text_field")
    assert text_input.display_name == "Custom Text Title"
    assert text_input.info == "A text field"
    assert isinstance(text_input, MessageTextInput)  # Check the instance type instead of field_type

    # Test number field
    number_input = find_input("number_field")
    assert number_input.display_name == "Number Field"
    assert number_input.info == "A number field"
    assert isinstance(number_input, IntInput | FloatInput)

    # Test boolean field
    bool_input = find_input("bool_field")
    assert isinstance(bool_input, BoolInput)

    # Test dictionary field
    dict_input = find_input("dict_field")
    assert isinstance(dict_input, DictInput)

    # Test list field
    list_input = find_input("list_field")
    assert list_input.is_list is True
    assert isinstance(list_input, MessageTextInput)


def test_schema_to_langflow_inputs_invalid_type():
    # Define a schema with an unsupported type
    class CustomType:
        pass

    class InvalidSchema(BaseModel):
        model_config = {"arbitrary_types_allowed": True}  # Add this line
        invalid_field: CustomType

    # Test that attempting to convert an unsupported type raises TypeError
    with pytest.raises(TypeError, match="Unsupported field type:"):
        schema_to_langflow_inputs(InvalidSchema)
