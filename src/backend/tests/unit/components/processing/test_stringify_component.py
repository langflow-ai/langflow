import pytest
from langflow.components.processing import StringifyComponent
from langflow.schema import Data, DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestStringifyComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return StringifyComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_data": Data(text="test string"),
            "clean_data": True,
            "session_id": "test_session",
            "sender": "test_sender",
            "sender_name": "test_sender_name",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions.

        Version compatibility:
        - Before 1.1.5: Component does not exist
        - 1.1.5 onwards: Component available in processing module
        - Latest tested: 1.2.0
        """

    def test_stringify_none_input(self):
        """Test validation with None input."""
        component = StringifyComponent()
        component.set_attributes({"input_data": None})
        with pytest.raises(ValueError, match="Input data cannot be None"):
            component.convert_to_string()

    def test_stringify_wrong_type(self):
        """Test validation with wrong input type."""
        component = StringifyComponent()
        component.set_attributes({"input_data": "wrong type"})
        with pytest.raises(TypeError, match="Expected Data or DataFrame"):
            component.convert_to_string()

    def test_stringify_data_object(self):
        """Test converting Data object."""
        component = StringifyComponent()
        component.set_attributes({"input_data": Data(text="test string")})
        result = component.convert_to_string()
        assert result.text == "test string"

    def test_stringify_empty_data_object(self):
        """Test converting empty Data object."""
        component = StringifyComponent()
        component.set_attributes({"input_data": Data(text=None)})
        with pytest.raises(ValueError, match="Empty Data object"):
            component.convert_to_string()

    def test_stringify_dataframe_basic(self):
        """Test converting basic DataFrame."""
        component = StringifyComponent()
        data_frame = DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        component.set_attributes({"input_data": data_frame, "clean_data": False})
        result = component.convert_to_string()
        assert "col1" in result.text
        assert "col2" in result.text
        assert "1" in result.text
        assert "2" in result.text
        assert "a" in result.text
        assert "b" in result.text

    def test_stringify_dataframe_with_cleaning(self):
        """Test DataFrame cleaning functionality."""
        component = StringifyComponent()
        data_frame = DataFrame({"col1": [1, None, 3], "col2": ["a", "", "c"], "col3": ["", "\n\n", "text"]})
        component.set_attributes({"input_data": data_frame, "clean_data": True})
        result = component.convert_to_string()

        # Check if empty rows are removed
        assert "None" not in result.text
        # Check if multiple newlines are replaced
        assert "\n\n" not in result.text
        # Check if content is preserved
        assert "1" in result.text
        assert "3" in result.text
        assert "a" in result.text
        assert "c" in result.text
        assert "text" in result.text

    def test_stringify_dataframe_without_cleaning(self):
        """Test DataFrame without cleaning."""
        component = StringifyComponent()
        data_frame = DataFrame({"col1": [1, None, 3], "col2": ["a", "", "c"]})
        component.set_attributes({"input_data": data_frame, "clean_data": False})
        result = component.convert_to_string()

        # Check if empty values are preserved
        assert "None" in result.text or "" in result.text
        # Check if content is preserved
        assert "1" in result.text
        assert "3" in result.text
        assert "a" in result.text
        assert "c" in result.text

    def test_stringify_dataframe_empty(self):
        """Test converting empty DataFrame."""
        component = StringifyComponent()
        data_frame = DataFrame()
        component.set_attributes({"input_data": data_frame})
        result = component.convert_to_string()
        assert result.text.strip() == ""
