import pandas as pd
import pytest
from langflow.components.processing.convertor import TypeConverterComponent
from langflow.schema import Data, DataFrame, Message

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
        assert isinstance(result.data, pd.DataFrame)
        assert "value" in result.data.columns
        assert result.data.iloc[0]["value"] == "Hello"

    # Data to other types
    def test_data_to_message(self, component_class):
        """Test converting Data to Message."""
        component = component_class(input_data=Data(data={"text": "Hello World"}), output_type="Message")
        result = component.convert_to_message()
        assert isinstance(result, Message)
        assert result.text == "{'text': 'Hello World'}"

    def test_data_to_data(self, component_class):
        """Test converting Data to Data."""
        component = component_class(input_data=Data(data={"key": "value"}), output_type="Data")
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert result.data == {"key": "value"}

    def test_data_to_dataframe(self, component_class):
        """Test converting Data to DataFrame."""
        component = component_class(input_data=Data(data={"key": "value"}), output_type="DataFrame")
        result = component.convert_to_dataframe()
        assert isinstance(result, DataFrame)
        assert isinstance(result.data, pd.DataFrame)
        assert "value" in result.data.columns
        assert result.data.iloc[0]["value"] == "{'key': 'value'}"

    # DataFrame to other types
    def test_dataframe_to_message(self, component_class):
        """Test converting DataFrame to Message."""
        test_df = pd.DataFrame({"col1": ["Hello"], "col2": ["World"]})
        component = component_class(input_data=DataFrame(test_df), output_type="Message")
        result = component.convert_to_message()
        assert isinstance(result, Message)
        assert result.text == "| col1   | col2   |\n|--------|--------|\n| Hello  | World  |"

    def test_dataframe_to_data(self, component_class):
        """Test converting DataFrame to Data."""
        test_df = pd.DataFrame({"col1": ["Hello"]})
        component = component_class(input_data=DataFrame(test_df), output_type="Data")
        result = component.convert_to_data()
        assert isinstance(result, Data)
        assert isinstance(result.data, dict)

    def test_dataframe_to_dataframe(self, component_class):
        """Test converting DataFrame to DataFrame."""
        test_df = pd.DataFrame({"col1": ["Hello"]})
        component = component_class(input_data=DataFrame(test_df), output_type="DataFrame")
        result = component.convert_to_dataframe()
        assert isinstance(result, DataFrame)
        assert isinstance(result.data, pd.DataFrame)
        assert "col1" in result.data.columns
        assert result.data.iloc[0]["col1"] == "Hello"

    # Additional helper tests
    def test_safe_convert(self, component_class):
        """Test the _safe_convert method."""
        component = component_class(input_data=Message(text="Hello"), output_type="Message")

        # Test with Message
        result = component._safe_convert(Message(text="Hello"))
        assert result == "Hello"

        # Test with Data
        result = component._safe_convert(Data(data={"text": "Hello"}))
        assert result == "{'text': 'Hello'}"

        # Test with DataFrame
        test_df = pd.DataFrame({"col1": ["Hello"]})
        result = component._safe_convert(DataFrame(test_df))
        assert "| col1   |" in result
        assert "| Hello  |" in result

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
