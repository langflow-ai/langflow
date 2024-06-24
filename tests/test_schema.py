from typing import Union

import pytest
from pydantic import ValidationError

from langflow.template import Input, Output
from langflow.template.field.base import UNDEFINED
from langflow.type_extraction.type_extraction import post_process_type


@pytest.fixture(name="client", autouse=True)
def client_fixture():
    pass


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
        assert post_process_type(int) == [int]
        assert post_process_type(list[int]) == [int]
        assert post_process_type(Union[int, str]) == [int, str]

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
            "password": False,
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
            "types": [],
            "name": "test_output",
            "display_name": "test_output",
            "cache": True,
            "value": "__UNDEFINED__",
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
        assert post_process_type(Union[int, str]) == [int, str]

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

        assert post_process_type(Union[CustomType, int]) == [CustomType, int]
