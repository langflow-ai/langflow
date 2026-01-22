import math

import pytest
from langflow.serialization.constants import MAX_TEXT_LENGTH
from lfx.utils.util_strings import truncate_long_strings


@pytest.mark.parametrize(
    ("input_data", "max_length", "expected"),
    [
        # Test case 1: String shorter than max_length
        ("short string", 20, "short string"),
        # Test case 2: String exactly at max_length
        ("exact", 5, "exact"),
        # Test case 3: String longer than max_length
        ("long string", 7, "long st..."),
        # Test case 4: Empty string
        ("", 5, ""),
        # Test case 5: Single character string
        ("a", 1, "a"),
        # Test case 6: Unicode string
        ("こんにちは", 3, "こんに..."),
        # Test case 7: Integer input
        (12345, 3, 12345),
        # Test case 8: Float input
        (math.pi, 4, math.pi),
        # Test case 9: Boolean input
        (True, 2, True),
        # Test case 10: None input
        (None, 5, None),
        # Test case 11: Very long string
        ("a" * 1000, 10, "a" * 10 + "..."),
    ],
)
def test_truncate_long_strings_non_dict_list(input_data, max_length, expected):
    result = truncate_long_strings(input_data, max_length)
    assert result == expected


# Test for max_length of 0
def test_truncate_long_strings_zero_max_length():
    assert truncate_long_strings("any string", 0) == "..."


# Test for negative max_length
def test_truncate_long_strings_negative_max_length():
    assert truncate_long_strings("any string", -1) == "any string"


# Test for None max_length (should use default MAX_TEXT_LENGTH)
def test_truncate_long_strings_none_max_length():
    long_string = "a" * (MAX_TEXT_LENGTH + 10)
    result = truncate_long_strings(long_string, None)
    assert len(result) == MAX_TEXT_LENGTH + 3  # +3 for "..."
    assert result == "a" * MAX_TEXT_LENGTH + "..."
