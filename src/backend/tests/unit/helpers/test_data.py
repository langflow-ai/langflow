import pytest
from langflow.helpers.data import data_to_text_list
from langflow.schema import Data


@pytest.mark.parametrize(
    (
        "template",
        "data",
        "expected",
    ),
    [
        (
            "{name} is {age} years old",
            Data(data={"name": "Alice", "age": 25}),
            (["Alice is 25 years old"], [Data(data={"name": "Alice", "age": 25})]),
        ),
        (
            "{name} is {age} years old",
            [
                Data(data={"name": "Alice", "age": 25}),
                Data(data={"name": "Bob", "age": 30}),
                Data(data={"name": "Alex", "age": 35}),
            ],
            (
                [
                    "Alice is 25 years old",
                    "Bob is 30 years old",
                    "Alex is 35 years old",
                ],
                [
                    Data(data={"name": "Alice", "age": 25}),
                    Data(data={"name": "Bob", "age": 30}),
                    Data(data={"name": "Alex", "age": 35}),
                ],
            ),
        ),
    ],
)
def test_data_to_text_list(template, data, expected):
    result = data_to_text_list(template, data)
    assert result == expected


def test_data_to_text_list__template_empty():
    template = ""
    data = Data(data={"key": "value"})

    result = data_to_text_list(template, data)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert isinstance(result[1], list)
    assert template in result[0]
    assert data in result[1]


def test_data_to_text_list__template_without_placeholder():
    template = "My favorite color is gray"
    data = Data(data={"color": "silver"})

    result = data_to_text_list(template, data)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert isinstance(result[1], list)
    assert template in result[0]
    assert data in result[1]


def test_data_to_text_list__template_without_placeholder_and_data_attribute_empty():
    template = "My favorite color is gray"
    data_list = [Data(data={})]

    result = data_to_text_list(template, data_list)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert isinstance(result[1], list)
    assert template in result[0]
    assert data_list == result[1]


def test_data_to_text_list__template_wrong_placeholder():
    template = "My favorite color is {color}"
    data = Data(data={"fruit": "apple"})

    # Should not raise KeyError due to defaultdict behavior
    result = data_to_text_list(template, data)
    assert result == (["My favorite color is "], [data])


def test_data_to_text_list__data_with_data_attribute_empty():
    template = "My favorite color is {color}"
    data = Data(data={})

    # Should not raise KeyError due to defaultdict behavior
    result = data_to_text_list(template, data)
    assert result == (["My favorite color is "], [data])


def test_data_to_text_list__data_contains_nested_data_key():
    template = "My data is: {data}"
    data = Data(data={"data": {"key": "value"}})

    result = data_to_text_list(template, data)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert isinstance(result[1], list)
    assert template not in result[0]
    assert data in result[1]
