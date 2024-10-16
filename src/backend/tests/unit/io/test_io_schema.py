from typing import TYPE_CHECKING, Literal

import pytest
from langflow.components.inputs.ChatInput import ChatInput

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def test_create_input_schema():
    from langflow.io.schema import create_input_schema

    schema = create_input_schema(ChatInput.inputs)
    assert schema.__name__ == "InputSchema"


class TestCreateInputSchema:
    # Single input type is converted to list and processed correctly
    def test_single_input_type_conversion(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field")
        schema = create_input_schema([input_instance])
        assert schema.__name__ == "InputSchema"
        assert "test_field" in schema.model_fields

    # Multiple input types are processed and included in the schema
    def test_multiple_input_types(self):
        from langflow.inputs.inputs import IntInput, StrInput
        from langflow.io.schema import create_input_schema

        inputs = [StrInput(name="str_field"), IntInput(name="int_field")]
        schema = create_input_schema(inputs)
        assert schema.__name__ == "InputSchema"
        assert "str_field" in schema.model_fields
        assert "int_field" in schema.model_fields

    # Fields are correctly created with appropriate types and attributes
    def test_fields_creation_with_correct_types_and_attributes(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field", info="Test Info", required=True)
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.description == "Test Info"
        assert field_info.is_required() is True

    # Schema model is created and returned successfully
    def test_schema_model_creation(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field")
        schema = create_input_schema([input_instance])
        assert schema.__name__ == "InputSchema"

    # Default values are correctly assigned to fields
    def test_default_values_assignment(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field", value="default_value")
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.default == "default_value"

    # Empty list of inputs is handled without errors
    def test_empty_list_of_inputs(self):
        from langflow.io.schema import create_input_schema

        schema = create_input_schema([])
        assert schema.__name__ == "InputSchema"

    # Input with missing optional attributes (e.g., display_name, info) is processed correctly
    def test_missing_optional_attributes(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field")
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.title == "Test Field"
        assert field_info.description == ""

    # Input with is_list attribute set to True is processed correctly
    def test_is_list_attribute_processing(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field", is_list=True)
        schema = create_input_schema([input_instance])
        field_info: FieldInfo = schema.model_fields["test_field"]
        assert field_info.annotation == list[str]

    # Input with options attribute is processed correctly
    def test_options_attribute_processing(self):
        from langflow.inputs.inputs import DropdownInput
        from langflow.io.schema import create_input_schema

        input_instance = DropdownInput(name="test_field", options=["option1", "option2"])
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.annotation == Literal["option1", "option2"]

    # Non-standard field types are handled correctly
    def test_non_standard_field_types_handling(self):
        from langflow.inputs.inputs import FileInput
        from langflow.io.schema import create_input_schema

        input_instance = FileInput(name="file_field")
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["file_field"]
        assert field_info.annotation is str

    # Inputs with mixed required and optional fields are processed correctly
    def test_mixed_required_optional_fields_processing(self):
        from langflow.inputs.inputs import IntInput, StrInput
        from langflow.io.schema import create_input_schema

        inputs = [
            StrInput(name="required_field", required=True),
            IntInput(name="optional_field", required=False),
        ]
        schema = create_input_schema(inputs)
        required_field_info = schema.model_fields["required_field"]
        optional_field_info = schema.model_fields["optional_field"]

        assert required_field_info.is_required() is True
        assert optional_field_info.is_required() is False

    # Inputs with complex nested structures are handled correctly
    def test_complex_nested_structures_handling(self):
        from langflow.inputs.inputs import NestedDictInput
        from langflow.io.schema import create_input_schema

        nested_input = NestedDictInput(name="nested_field", value={"key": "value"})
        schema = create_input_schema([nested_input])

        field_info = schema.model_fields["nested_field"]

        assert isinstance(field_info.default, dict)
        assert field_info.default["key"] == "value"

    # Creating a schema from a single input type
    def test_single_input_type_replica(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field")
        schema = create_input_schema([input_instance])
        assert schema.__name__ == "InputSchema"
        assert "test_field" in schema.model_fields

    # Creating a schema from a list of input types
    def test_passing_input_type_directly(self):
        from langflow.inputs.inputs import IntInput, StrInput
        from langflow.io.schema import create_input_schema

        inputs = StrInput(name="str_field"), IntInput(name="int_field")
        with pytest.raises(TypeError):
            create_input_schema(inputs)

    # Handling input types with options correctly
    def test_options_handling(self):
        from langflow.inputs.inputs import DropdownInput
        from langflow.io.schema import create_input_schema

        input_instance = DropdownInput(name="test_field", options=["option1", "option2"])
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.annotation == Literal["option1", "option2"]

    # Handling input types with is_list attribute correctly
    def test_is_list_handling(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field", is_list=True)
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.annotation == list[str]  # type: ignore

    # Converting FieldTypes to corresponding Python types
    def test_field_types_conversion(self):
        from langflow.inputs.inputs import IntInput
        from langflow.io.schema import create_input_schema

        input_instance = IntInput(name="int_field")
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["int_field"]
        assert field_info.annotation is int  # Use 'is' for type comparison

    # Setting default values for non-required fields
    def test_default_values_for_non_required_fields(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field", value="default_value")
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.default == "default_value"

    # Handling input types with missing attributes
    def test_missing_attributes_handling(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field")
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.title == "Test Field"
        assert field_info.description == ""

    # Handling invalid field types

    # Handling input types with None as default value
    def test_none_default_value_handling(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test_field", value=None)
        schema = create_input_schema([input_instance])
        field_info = schema.model_fields["test_field"]
        assert field_info.default is None

    # Handling input types with special characters in names
    def test_special_characters_in_names_handling(self):
        from langflow.inputs.inputs import StrInput
        from langflow.io.schema import create_input_schema

        input_instance = StrInput(name="test@field#name")
        schema = create_input_schema([input_instance])
        assert "test@field#name" in schema.model_fields
