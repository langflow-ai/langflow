import pytest
from langflow.helpers.data import data_to_text_list
from langflow.schema import JSON


@pytest.mark.parametrize(
    ("template", "data", "expected_text"),
    [
        # Test basic string data
        (
            "Text: {text}",
            JSON(text="Hello"),
            ["Text: Hello"],
        ),
        # Test dictionary data
        (
            "{name} is {age} years old",
            JSON(data={"name": "Alice", "age": 25}),
            ["Alice is 25 years old"],
        ),
        # Test list of Data objects
        (
            "{name} is {age} years old",
            [
                JSON(data={"name": "Alice", "age": 25}),
                JSON(data={"name": "Bob", "age": 30}),
            ],
            ["Alice is 25 years old", "Bob is 30 years old"],
        ),
        # Test nested data dictionary
        (
            "User: {text}",
            JSON(data={"data": {"text": "Hello World"}}),
            ["User: Hello World"],
        ),
        # Test error message in data
        (
            "Error: {text}",
            JSON(data={"error": "Something went wrong"}),
            ["Error: Something went wrong"],
        ),
        # Test non-Data object conversion
        (
            "Value: {text}",
            JSON(text="Simple string"),
            ["Value: Simple string"],
        ),
    ],
)
def test_data_to_text_list_parametrized(template, data, expected_text):
    """Test various input combinations for data_to_text_list."""
    result = data_to_text_list(template, data)
    assert result[0] == expected_text
    assert all(isinstance(d, JSON) for d in result[1])


def test_data_to_text_list_none_data():
    """Test handling of None data input."""
    result = data_to_text_list("template", None)
    assert result == ([], [])


def test_data_to_text_list_none_template():
    """Test handling of None template input."""
    with pytest.raises(ValueError, match="Template must be a string, but got None"):
        data_to_text_list(None, JSON(text="test"))


def test_data_to_text_list_invalid_template_type():
    """Test handling of invalid template type."""
    with pytest.raises(TypeError, match="Template must be a string, but got"):
        data_to_text_list(123, JSON(text="test"))


def test_data_to_text_list_missing_key():
    """Test handling of missing template key."""
    template = "Hello {missing_key}"
    data = JSON(data={"existing_key": "value"})
    # Should not raise KeyError due to defaultdict
    result = data_to_text_list(template, data)
    assert result == (["Hello "], [data])


def test_data_to_text_list_empty_data_dict():
    """Test handling of empty data dictionary."""
    template = "Hello {text}"
    data = JSON(data={})
    result = data_to_text_list(template, data)
    assert result == (["Hello "], [data])


def test_data_to_text_list_mixed_data_types():
    """Test handling of mixed data types in list."""
    template = "Item: {text}"
    data = [
        JSON(text="First"),
        "Second",
        JSON(data={"text": "Third"}),
        123,
    ]
    result = data_to_text_list(template, data)
    expected_texts = [
        "Item: First",
        "Item: Second",
        "Item: Third",
        "Item: 123",
    ]
    assert result[0] == expected_texts
    assert len(result[1]) == 4
    assert all(isinstance(d, JSON) for d in result[1])


def test_data_to_text_list_complex_nested_data():
    """Test handling of complex nested data structures."""
    template = "Name: {name}, Info: {text}, Status: {status}"
    data = JSON(data={"name": "Test", "data": {"text": "Nested text", "status": "active"}})
    result = data_to_text_list(template, data)
    expected = (["Name: Test, Info: Nested text, Status: active"], [data])
    assert result == expected


def test_data_to_text_list_empty_template():
    """Test handling of empty template string."""
    data = JSON(data={"key": "value"})
    result = data_to_text_list("", data)
    assert result == ([""], [data])


def test_data_to_text_list_string_data():
    """Test handling of string data in Data object."""
    template = "Message: {text}"
    data = JSON(data={"text": "Direct string"})
    result = data_to_text_list(template, data)
    assert result == (["Message: Direct string"], [data])
