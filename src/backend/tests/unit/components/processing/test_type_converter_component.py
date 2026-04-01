import json
from io import StringIO

import pandas as pd
import pytest
from lfx.components.processing.converter import TypeConverterComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestTypeConverterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return TypeConverterComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    # Message to other types
    def test_message_to_message(self, component_class):
        """Test converting Message to Message."""
        component = component_class(input_data=Message(text="Hello World"), output_type="Message")
        result = component.convert_to_message()
        assert isinstance(result, Message)
        assert result.text == "Hello World"

    def test_message_to_data(self, component_class):
        """Test converting Message to Data."""
        component = component_class(input_data=Message(text="Hello"), output_type="Data")
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert result.data == {"text": "Hello"}

    def test_message_to_dataframe(self, component_class):
        """Test converting Message to DataFrame."""
        component = component_class(input_data=Message(text="Hello"), output_type="DataFrame")
        result = component.convert_to_dataframe()
        assert isinstance(result, DataFrame)
        assert list(result.columns) == ["text"]
        assert result.iloc[0]["text"] == "Hello"

    # Data to other types
    def test_data_to_message(self, component_class):
        """Test converting Data to Message."""
        component = component_class(input_data=Data(data={"text": "Hello World"}), output_type="Message")
        result = component.convert_to_message()
        assert isinstance(result, Message)
        assert result.text == "Hello World"

    def test_data_to_data(self, component_class):
        """Test converting Data to Data."""
        component = component_class(input_data=Data(data={"key": "value"}), output_type="Data")
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert result.data == {"key": "value"}

    def test_data_to_dataframe(self, component_class):
        """Test converting Data to DataFrame."""
        component = component_class(input_data=Data(data={"text": "Hello World"}), output_type="DataFrame")
        result = component.convert_to_dataframe()
        assert isinstance(result, DataFrame)
        assert "text" in result.columns
        assert result.iloc[0]["text"] == "Hello World"

    # DataFrame to other types
    def test_dataframe_to_message(self, component_class):
        """Test converting DataFrame to Message."""
        df_data = pd.DataFrame({"col1": ["Hello"], "col2": ["World"]})
        component = component_class(input_data=DataFrame(data=df_data), output_type="Message")
        result = component.convert_to_message()
        assert isinstance(result, Message)
        assert result.text == "| col1   | col2   |\n|:-------|:-------|\n| Hello  | World  |"

    def test_dataframe_to_data(self, component_class):
        """Test converting DataFrame to Data."""
        df_data = pd.DataFrame({"col1": ["Hello"]})
        component = component_class(input_data=DataFrame(data=df_data), output_type="Data")
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert isinstance(result.data, dict)

    def test_dataframe_to_dataframe(self, component_class):
        """Test converting DataFrame to DataFrame."""
        df_data = pd.DataFrame({"col1": ["Hello"], "col2": ["World"]})
        component = component_class(input_data=DataFrame(data=df_data), output_type="DataFrame")
        result = component.convert_to_dataframe()
        assert isinstance(result, DataFrame)
        assert "col1" in result.columns
        assert "col2" in result.columns
        assert result.iloc[0]["col1"] == "Hello"
        assert result.iloc[0]["col2"] == "World"

    def test_update_outputs(self, component_class):
        """Test the update_outputs method."""
        component = component_class(input_data=Message(text="Hello"), output_type="Message")
        frontend_node = {"outputs": []}

        # Test with Message output
        updated = component.update_outputs(frontend_node, "output_type", "Message")
        assert len(updated["outputs"]) == 1
        assert updated["outputs"][0]["name"] == "message_output"

        # Test with Data output
        updated = component.update_outputs(frontend_node, "output_type", "Data")
        assert len(updated["outputs"]) == 1
        assert updated["outputs"][0]["name"] == "data_output"

        # Test with DataFrame output
        updated = component.update_outputs(frontend_node, "output_type", "DataFrame")
        assert len(updated["outputs"]) == 1
        assert updated["outputs"][0]["name"] == "dataframe_output"

    def test_message_with_valid_json_text_to_data(self, component_class):
        """Test converting Message to Data."""
        valid_json_text = '{"foo": "bar"}'
        component = component_class(input_data=Message(text=valid_json_text), output_type="Data", auto_parse=True)
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert result.data == json.loads(valid_json_text)

    def test_message_with_invalid_json_text_to_data(self, component_class):
        """Test converting Message to Data."""
        invalid_json_text = '{"foo", "bar"}'
        component = component_class(input_data=Message(text=invalid_json_text), output_type="Data", auto_parse=True)
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert isinstance(result.data["text"], str)
        assert result.data == {"text": invalid_json_text}

    def test_message_with_valid_json_array_to_data(self, component_class):
        """Test converting Message with JSON array to Data."""
        valid_json_text = '[{"name": "Ana", "age": 28}, {"name": "Bruno", "age": 34}]'
        component = component_class(input_data=Message(text=valid_json_text), output_type="Data", auto_parse=True)
        result = component.convert_to_data()

        expected_data = {"records": json.loads(valid_json_text)}

        assert isinstance(result, Data)
        assert result.data == expected_data

    def test_message_with_valid_csv_to_data(self, component_class):
        """Test converting Message with CSV to Data."""
        valid_csv_text = "name,age,email\nAna,28,ana@email.com\nBruno,34,bruno@email.com\nCarla,22,carla@email.com\n"
        component = component_class(input_data=Message(text=valid_csv_text), output_type="Data", auto_parse=True)
        result = component.convert_to_data()

        expected_data = {
            "records": [
                {"name": "Ana", "age": 28, "email": "ana@email.com"},
                {"name": "Bruno", "age": 34, "email": "bruno@email.com"},
                {"name": "Carla", "age": 22, "email": "carla@email.com"},
            ]
        }

        assert isinstance(result, Data)
        assert result.data == expected_data

    def test_message_with_valid_csv_to_dataframe(self, component_class):
        """Test converting Message to DataFrame."""
        valid_csv_text = (
            "name,age,email,city\n"
            "Ana,28,ana@email.com,São Paulo\n"
            "Bruno,34,bruno@email.com,Rio de Janeiro\n"
            "Carla,22,carla@email.com,Belo Horizonte\n"
            "Diego,40,diego@email.com,Curitiba\n"
            "Elisa,31,elisa@email.com,Porto Alegre\n"
        )
        component = component_class(input_data=Message(text=valid_csv_text), output_type="DataFrame", auto_parse=True)
        result = component.convert_to_dataframe()
        expected = pd.read_csv(StringIO(valid_csv_text))
        assert isinstance(result, DataFrame)
        assert list(result.columns) == ["name", "age", "email", "city"]
        pd.testing.assert_frame_equal(result, expected)

    def test_message_with_valid_json_object_to_dataframe(self, component_class):
        """Test converting Message with JSON object to DataFrame."""
        valid_json_text = '{"name": "Ana", "age": 28, "email": "ana@email.com", "city": "São Paulo"}'
        component = component_class(input_data=Message(text=valid_json_text), output_type="DataFrame", auto_parse=True)
        result = component.convert_to_dataframe()

        expected_data = [json.loads(valid_json_text)]
        expected = pd.DataFrame(expected_data)

        assert isinstance(result, DataFrame)
        assert list(result.columns) == ["name", "age", "email", "city"]
        pd.testing.assert_frame_equal(result, expected)

    def test_message_with_valid_json_array_to_dataframe(self, component_class):
        """Test converting Message with JSON array to DataFrame."""
        valid_json_text = """[
            {"name": "Ana", "age": 28, "email": "ana@email.com", "city": "São Paulo"},
            {"name": "Bruno", "age": 34, "email": "bruno@email.com", "city": "Rio de Janeiro"},
            {"name": "Carla", "age": 22, "email": "carla@email.com", "city": "Belo Horizonte"}
        ]"""
        component = component_class(input_data=Message(text=valid_json_text), output_type="DataFrame", auto_parse=True)
        result = component.convert_to_dataframe()

        expected_data = json.loads(valid_json_text)
        expected = pd.DataFrame(expected_data)

        assert isinstance(result, DataFrame)
        assert list(result.columns) == ["name", "age", "email", "city"]
        assert len(result) == 3
        pd.testing.assert_frame_equal(result, expected)

    def test_message_with_compact_json_array_to_dataframe(self, component_class):
        """Test converting Message with compact JSON array to DataFrame."""
        valid_json_text = '[{"name":"Ana","age":28},{"name":"Bruno","age":34},{"name":"Carla","age":22}]'
        component = component_class(input_data=Message(text=valid_json_text), output_type="DataFrame", auto_parse=True)
        result = component.convert_to_dataframe()

        expected_data = json.loads(valid_json_text)
        expected = pd.DataFrame(expected_data)

        assert isinstance(result, DataFrame)
        assert list(result.columns) == ["name", "age"]
        assert len(result) == 3
        pd.testing.assert_frame_equal(result, expected)
