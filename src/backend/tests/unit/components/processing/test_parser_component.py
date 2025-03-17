import pytest
from langflow.components.processing.parser import ParserComponent
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestParserComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return ParserComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_data": DataFrame({"Name": ["John"], "Age": [30], "Country": ["USA"]}),
            "template": "Name: {Name}, Age: {Age}, Country: {Country}",
            "sep": "\n",
            "stringify": False,
            "clean_data": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_parse_dataframe(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        assert result.text == "Name: John, Age: 30, Country: USA"

    def test_parse_data_object(self, component_class):
        # Arrange
        data = Data(text="Hello World")
        kwargs = {
            "input_data": data,
            "template": "text: {text}",
            "sep": "\n",
            "stringify": False,
        }
        component = component_class(**kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        assert result.text == "text: Hello World"

    def test_stringify_dataframe(self, component_class):
        # Arrange
        data_frame = DataFrame({"Name": ["John", "Jane"], "Age": [30, 25]})
        kwargs = {
            "input_data": data_frame,
            "stringify": True,
            "clean_data": False,
        }
        component = component_class(**kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        assert "| Name   |   Age |" in result.text
        assert "| John   |    30 |" in result.text
        assert "| Jane   |    25 |" in result.text

    def test_stringify_data_object(self, component_class):
        # Arrange
        data = Data(text="Hello\nWorld\nMultiline\nText")
        kwargs = {
            "input_data": data,
            "stringify": True,
            "clean_data": True,
        }
        component = component_class(**kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        assert "Hello" in result.text
        assert "World" in result.text
        assert "Multiline" in result.text
        assert "Text" in result.text

    def test_stringify_message_object(self, component_class):
        # Arrange
        message = Message(text="Test message content")
        kwargs = {
            "input_data": message,
            "stringify": True,
        }
        component = component_class(**kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        assert result.text == "Test message content"

    def test_clean_data_with_stringify(self, component_class):
        # Arrange
        data_frame = DataFrame(
            {"Name": ["John", "Jane\n", "\nBob"], "Age": [30, None, 25], "Notes": ["Good\n\nPerson", "", "Nice\n"]}
        )
        kwargs = {
            "input_data": data_frame,
            "stringify": True,
            "clean_data": True,
        }
        component = component_class(**kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        # Check for table structure
        assert "| Name" in result.text
        assert "|   Age" in result.text
        assert "| Notes" in result.text
        # Check for cleaned data
        assert "| John" in result.text
        assert "| Jane" in result.text
        assert "| Bob" in result.text
        assert "| Good" in result.text
        assert "| Person" in result.text
        assert "| Nice" in result.text
        # Verify data is cleaned
        assert "Jane\n" not in result.text
        assert "\nBob" not in result.text
        assert "Good\n\nPerson" not in result.text
        assert "Nice\n" not in result.text

    def test_invalid_input_type(self, component_class):
        # Arrange
        kwargs = {
            "input_data": 123,  # Invalid input type
            "template": "{value}",
            "sep": "\n",
        }
        component = component_class(**kwargs)

        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported input type: <class 'int'>. Expected DataFrame or Data."):
            component.parse_combined_text()

    def test_none_input(self, component_class):
        # Arrange
        kwargs = {
            "input_data": None,
            "template": "{value}",
            "sep": "\n",
        }
        component = component_class(**kwargs)

        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported input type: <class 'NoneType'>. Expected DataFrame or Data."):
            component.parse_combined_text()

    def test_invalid_template(self, component_class):
        # Arrange
        data_frame = DataFrame({"Name": ["John"]})
        kwargs = {
            "input_data": data_frame,
            "template": "{InvalidColumn}",  # Invalid column name
            "sep": "\n",
            "stringify": False,
        }
        component = component_class(**kwargs)

        # Act & Assert
        with pytest.raises(KeyError):
            component.parse_combined_text()

    def test_multiple_rows_with_custom_separator(self, component_class):
        # Arrange
        data_frame = DataFrame(
            {
                "Name": ["John", "Jane", "Bob"],
                "Age": [30, 25, 35],
            }
        )
        kwargs = {
            "input_data": data_frame,
            "template": "{Name} is {Age} years old",
            "sep": " | ",
            "stringify": False,
        }
        component = component_class(**kwargs)

        # Act
        result = component.parse_combined_text()

        # Assert
        assert isinstance(result, Message)
        expected = "John is 30 years old | Jane is 25 years old | Bob is 35 years old"
        assert result.text == expected
