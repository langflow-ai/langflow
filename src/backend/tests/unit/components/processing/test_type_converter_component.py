import pandas as pd
import pytest
from langflow.components.processing.converter import TypeConverterComponent
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message

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
        assert "text" in result.data
        assert result.data["text"] == "Hello"

    def test_message_to_dataframe(self, component_class):
        """Test converting Message to DataFrame."""
        component = component_class(input_data=Message(text="Hello"), output_type="DataFrame")
        result = component.convert_to_dataframe()
        assert isinstance(result, DataFrame)
        assert "text" in result.columns
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
