import pytest
from langflow.inputs.inputs import DataFrameInput, DataInput, MessageInput, MessageTextInput
from langflow.schema import Data, DataFrame, Message


class TestDataInput:
    """Test suite for DataInput class data conversion."""

    def test_validate_value_dataframe(self):
        """Test conversion from DataFrame to Data."""
        user_data_dataframe = DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})
        input_obj = DataInput(name="test_input", value=user_data_dataframe)
        assert isinstance(input_obj.value, Data)
        assert "results" in input_obj.value.data
        assert len(input_obj.value.data["results"]) == 2
        assert input_obj.value.data["results"][0]["name"] == "Alice"

    def test_validate_value_message(self):
        """Test conversion from Message to Data."""
        message = Message(text="Hello")
        data = Data(data=message.data)
        input_obj = DataInput(name="test_input", value=message)
        assert isinstance(input_obj.value, Data)
        assert input_obj.value == data

    def test_validate_value_dict(self):
        """Test conversion from dict to Data."""
        data_dict = {"key": "value"}
        input_obj = DataInput(name="test_input", value=data_dict)
        assert isinstance(input_obj.value, Data)
        assert input_obj.value.data == data_dict

    def test_validate_value_data(self):
        """Test when value is already a Data object."""
        data = Data(data={"key": "value"})
        input_obj = DataInput(name="test_input", value=data)
        assert input_obj.value == data

    def test_validate_value_invalid_type(self):
        """Test validation with invalid input type."""
        with pytest.raises(ValueError, match="Invalid value type .* for input test_input. Expected Data."):
            DataInput(name="test_input", value=123)


class TestMessageInput:
    """Test suite for MessageInput class data conversion."""

    def test_validate_value_dict(self):
        """Test conversion from dict to Message."""
        # Test with a simple dict containing just text and a data key
        data_dict = {"text": "Hello", "data": {"key": "value"}}
        input_obj = MessageInput(name="test_input", value=data_dict)

        # Verify the input was converted to a Message object
        assert isinstance(input_obj.value, Message)

        # Verify the basic properties were transferred
        assert input_obj.value.text == "Hello"

        # Verify that the Message object has all the expected properties
        # that are automatically added during conversion
        assert hasattr(input_obj.value, "category")
        assert hasattr(input_obj.value, "content_blocks")
        assert hasattr(input_obj.value, "edit")
        assert hasattr(input_obj.value, "error")
        assert hasattr(input_obj.value, "files")
        assert hasattr(input_obj.value, "flow_id")
        assert hasattr(input_obj.value, "properties")
        assert hasattr(input_obj.value, "sender")
        assert hasattr(input_obj.value, "sender_name")
        assert hasattr(input_obj.value, "session_id")
        assert hasattr(input_obj.value, "timestamp")

    def test_validate_value_message(self):
        """Test when value is already a Message object."""
        message = Message(text="Hello")
        input_obj = MessageInput(name="test_input", value=message)
        assert input_obj.value == message

    def test_validate_value_string(self):
        """Test conversion from string to Message."""
        input_obj = MessageInput(name="test_input", value="Hello")
        assert isinstance(input_obj.value, Message)
        assert input_obj.value.text == "Hello"

    def test_validate_value_dataframe(self):
        """Test conversion from DataFrame to Message."""
        example_df = DataFrame({"name": ["Alice"], "age": [25]})
        input_obj = MessageInput(name="test_input", value=example_df)
        assert isinstance(input_obj.value, Message)
        # Check that the DataFrame was converted to a markdown table format
        assert "name" in input_obj.value.text
        assert "age" in input_obj.value.text
        assert "Alice" in input_obj.value.text
        assert "25" in input_obj.value.text
        # Verify table structure without relying on exact spacing
        assert "|" in input_obj.value.text
        assert "-" in input_obj.value.text

    def test_validate_value_data(self):
        """Test conversion from Data to Message."""
        data = Data(data={"text": "Hello"})
        input_obj = MessageInput(name="test_input", value=data)
        assert isinstance(input_obj.value, Message)
        assert input_obj.value.text == "Hello"


class TestMessageTextInput:
    """Test suite for MessageTextInput class data conversion."""

    def test_validate_value_dict(self):
        """Test conversion from dict to text."""
        data_dict = {"text": "Hello"}
        input_obj = MessageTextInput(name="test_input", value=data_dict)
        assert input_obj.value == "Hello"

    def test_validate_value_message(self):
        """Test conversion from Message to text."""
        message = Message(text="Hello")
        input_obj = MessageTextInput(name="test_input", value=message)
        assert input_obj.value == "Hello"

    def test_validate_value_string(self):
        """Test when value is already a string."""
        input_obj = MessageTextInput(name="test_input", value="Hello")
        assert input_obj.value == "Hello"

    def test_validate_value_dataframe(self):
        """Test conversion from DataFrame to text."""
        example_df = DataFrame({"name": ["Alice"], "age": [25]})
        input_obj = MessageTextInput(name="test_input", value=example_df)
        assert isinstance(input_obj.value, str)
        # Check that the DataFrame was converted to a markdown table format
        assert "name" in input_obj.value
        assert "age" in input_obj.value
        assert "Alice" in input_obj.value
        assert "25" in input_obj.value
        # Verify table structure without relying on exact spacing
        assert "|" in input_obj.value
        assert "-" in input_obj.value

    def test_validate_value_data_with_text_key(self):
        """Test conversion from Data with text_key to text."""
        data = Data(data={"text": "Hello"})
        input_obj = MessageTextInput(name="test_input", value=data)
        assert input_obj.value == "Hello"

    def test_validate_value_data_missing_text_key(self):
        """Test conversion from Data without text_key raises error."""
        data = Data(data={"other_key": "value"})
        with pytest.raises(ValueError, match="must contain the key 'text'"):
            MessageTextInput(name="test_input", value=data)


class TestDataFrameInput:
    """Test suite for DataFrameInput class data conversion."""

    def test_validate_value_data_with_list(self):
        """Test conversion from Data with list to DataFrame."""
        data = Data(data={"results": [{"name": "Alice", "age": 25}]})
        input_obj = DataFrameInput(name="test_input", value=data)
        assert isinstance(input_obj.value, DataFrame)
        assert len(input_obj.value) == 1
        assert input_obj.value.iloc[0]["name"] == "Alice"

    def test_validate_value_data_single_item(self):
        """Test conversion from single Data item to DataFrame."""
        data = Data(data={"key": "value"})
        input_obj = DataFrameInput(name="test_input", value=data)
        assert isinstance(input_obj.value, DataFrame)
        assert len(input_obj.value) == 1
        assert input_obj.value.iloc[0]["key"] == "value"

    def test_validate_value_message(self):
        """Test conversion from Message to DataFrame."""
        message = Message(text="Hello", data={"key": "value"})
        input_obj = DataFrameInput(name="test_input", value=message)
        assert isinstance(input_obj.value, DataFrame)
        assert len(input_obj.value) == 1
        assert input_obj.value.iloc[0]["text"] == "Hello"

    def test_validate_value_dict(self):
        """Test conversion from dict to DataFrame."""
        data_dict = {"name": "Alice", "age": 25}
        input_obj = DataFrameInput(name="test_input", value=data_dict)
        assert isinstance(input_obj.value, DataFrame)
        assert len(input_obj.value) == 1
        assert input_obj.value.iloc[0]["name"] == "Alice"

    def test_validate_value_dataframe(self):
        """Test when value is already a DataFrame."""
        age_name_dataframe = DataFrame({"name": ["Alice"], "age": [25]})
        input_obj = DataFrameInput(name="test_input", value=age_name_dataframe)
        assert input_obj.value.equals(age_name_dataframe)

    def test_validate_value_invalid_type(self):
        """Test validation with invalid input type."""
        with pytest.raises(ValueError, match="Invalid value type .* for input test_input. Expected DataFrame."):
            DataFrameInput(name="test_input", value=123)
