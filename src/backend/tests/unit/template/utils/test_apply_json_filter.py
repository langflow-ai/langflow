import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from langflow.schema.data import Data
from langflow.template.utils import apply_json_filter


# Helper function to create nested dictionaries
def dict_strategy():
    return st.recursive(
        st.one_of(st.integers(), st.text(), st.floats(allow_nan=False, allow_infinity=False), st.booleans()),
        lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(), children, max_size=5),
        max_leaves=10,
    )


# Test basic dictionary access
@given(data=st.dictionaries(st.text(), st.integers()), key=st.text())
def test_basic_dict_access(data, key):
    # Skip empty key tests which have special handling
    assume(key != "")

    if key in data:
        result = apply_json_filter(data, key)
        assert result == data[key]
    else:
        result = apply_json_filter(data, key)
        assert result is None


# Test array access
@given(data=st.lists(st.integers(), min_size=1), index=st.integers())
def test_array_access(data, index):
    filter_str = f"[{index}]"
    result = apply_json_filter(data, filter_str)
    if 0 <= index < len(data):
        assert result == data[index]
    else:
        assert result is None


# Test nested object access
@given(nested_data=dict_strategy())
def test_nested_object_access(nested_data):
    # Skip non-dictionary inputs that would cause Data validation errors
    assume(isinstance(nested_data, dict))

    # Wrap in Data object to test both raw and Data object inputs
    data_obj = Data(data=nested_data)
    result = apply_json_filter(data_obj, "")
    assert result == nested_data


# Test edge cases
@pytest.mark.parametrize(
    ("input_data", "filter_str", "expected"),
    [
        ({}, "", {}),  # Empty dict, empty filter
        ([], "", []),  # Empty list, empty filter
        (None, "any.path", None),  # None input
        ({"a": 1}, None, {"a": 1}),  # None filter
        ({"a": 1}, "   ", {"a": 1}),  # Whitespace filter
    ],
)
def test_edge_cases(input_data, filter_str, expected):
    result = apply_json_filter(input_data, filter_str)
    assert result == expected


# Test complex nested access
@given(data=st.dictionaries(keys=st.text(), values=st.dictionaries(keys=st.text(), values=st.lists(st.integers()))))
def test_complex_nested_access(data):
    if data:
        outer_key = next(iter(data))
        if data[outer_key]:
            inner_key = next(iter(data[outer_key]))
            filter_str = f"{outer_key}.{inner_key}"
            result = apply_json_filter(data, filter_str)
            assert result == data[outer_key][inner_key]


# Test array operations on objects
@given(
    data=st.lists(
        st.dictionaries(
            keys=st.text(min_size=1).filter(lambda s: s.strip() and not any(c in s for c in "\r\n\t")),
            values=st.integers(),
            min_size=1,
        ),
        min_size=1,
    )
)
def test_array_object_operations(data):
    if data and all(data):
        key = next(iter(data[0]))
        # Skip empty key tests which have special handling
        assume(key != "")
        result = apply_json_filter(data, key)
        expected = [item[key] for item in data if key in item]
        assert result == expected


# Test invalid inputs
@pytest.mark.parametrize(
    ("input_data", "filter_str"),
    [
        ({"a": 1}, "[invalid]"),  # Invalid array index
        ([1, 2, 3], "nonexistent"),  # Nonexistent key on array
        ({"a": 1}, "..[invalid]"),  # Invalid syntax
    ],
)
def test_invalid_inputs(input_data, filter_str):
    result = apply_json_filter(input_data, filter_str)
    assert result is None or isinstance(result, dict | list | Data)
