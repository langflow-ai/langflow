import pytest
from langflow.serialization.constants import MAX_TEXT_LENGTH

from lfx.utils.util_strings import truncate_long_strings


@pytest.mark.parametrize(
    ("input_data", "max_length", "expected"),
    [
        # Test case 1: Simple string truncation
        ({"key": "a" * 100}, 10, {"key": "a" * 10 + "..."}),
        # Test case 2: Nested dictionary
        ({"outer": {"inner": "b" * 100}}, 5, {"outer": {"inner": "b" * 5 + "..."}}),
        # Test case 3: List of strings
        (["short", "a" * 100, "also short"], 7, ["short", "a" * 7 + "...", "also sh" + "..."]),
        # Test case 4: Mixed nested structure
        (
            {"key1": ["a" * 100, {"nested": "b" * 100}], "key2": "c" * 100},
            8,
            {"key1": ["a" * 8 + "...", {"nested": "b" * 8 + "..."}], "key2": "c" * 8 + "..."},
        ),
        # Test case 5: Empty structures
        ({}, 10, {}),
        ([], 10, []),
        # Test case 6: Strings at exact max_length
        ({"exact": "a" * 10}, 10, {"exact": "a" * 10}),
        # Test case 7: Non-string values
        ({"num": 12345, "bool": True, "none": None}, 5, {"num": 12345, "bool": True, "none": None}),
        # Test case 8: Unicode characters
        ({"unicode": "こんにちは世界"}, 3, {"unicode": "こんに..."}),
        # Test case 9: Very large structure
        (
            {"key" + str(i): "value" * i for i in range(1000)},
            10,
            {"key" + str(i): ("value" * i)[:10] + "..." if len("value" * i) > 10 else "value" * i for i in range(1000)},
        ),
    ],
)
def test_truncate_long_strings(input_data, max_length, expected):
    result = truncate_long_strings(input_data, max_length)
    assert result == expected


def test_truncate_long_strings_default_max_length():
    long_string = "a" * (MAX_TEXT_LENGTH + 1)
    input_data = {"key": long_string}
    result = truncate_long_strings(input_data)
    assert len(result["key"]) == MAX_TEXT_LENGTH + 3  # +3 for the "..."


def test_truncate_long_strings_no_modification():
    input_data = {"short": "short string", "nested": {"also_short": "another short string"}}
    result = truncate_long_strings(input_data, 100)
    assert result == input_data


# Test for type preservation
def test_truncate_long_strings_type_preservation():
    input_data = {"str": "a" * 100, "list": ["b" * 100], "dict": {"nested": "c" * 100}}
    result = truncate_long_strings(input_data, 10)
    assert isinstance(result, dict)
    assert isinstance(result["str"], str)
    assert isinstance(result["list"], list)
    assert isinstance(result["dict"], dict)


# Test for in-place modification
def test_truncate_long_strings_in_place_modification():
    input_data = {"key": "a" * 100}
    result = truncate_long_strings(input_data, 10)
    assert result is input_data  # Check if the same object is returned


# Test for invalid input
def test_truncate_long_strings_invalid_input():
    input_string = "not a dict or list"
    result = truncate_long_strings(input_string, 10)
    assert result == "not a dict..."  # The function should truncate the string


# Updated test for negative max_length
def test_truncate_long_strings_negative_max_length():
    input_data = {"key": "value"}
    result = truncate_long_strings(input_data, -1)
    assert result == input_data  # Assuming the function ignores negative max_length


# Additional test for zero max_length
def test_truncate_long_strings_zero_max_length():
    input_data = {"key": "value"}
    result = truncate_long_strings(input_data, 0)
    assert result == {"key": "..."}  # Assuming the function truncates to just "..."


# Test for very small positive max_length
def test_truncate_long_strings_small_max_length():
    input_data = {"key": "value"}
    result = truncate_long_strings(input_data, 1)
    assert result == {"key": "v..."}  # Assuming the function keeps at least one character
