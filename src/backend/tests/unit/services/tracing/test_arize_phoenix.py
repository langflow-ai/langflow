import os
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

import pytest
from lfx.schema.data import Data

from src.backend.base.langflow.services.tracing.arize_phoenix import (
    ArizePhoenixTracer,
)


@pytest.fixture
def tracer():
    return ArizePhoenixTracer.__new__(ArizePhoenixTracer)


def test_data_dict_conversion(tracer):
    value = Data(data={"a": 1, "b": "x"})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"a": 1, "b": "x"}


def test_data_list_conversion(tracer):
    value = Data(data=[1, 2, 3])

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == [1, 2, 3]


def test_data_text_fallback(tracer):
    value = Data(data="hello")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == value.get_text()


def test_data_nested_structure(tracer):
    value = Data(data={"nested": [1, {"x": 2}]})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"nested": [1, {"x": 2}]}


def test_data_none(tracer):
    value = Data(data=None)

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == value.get_text()


def test_dict_recursive_conversion(tracer):
    value = {
        "a": Data(data={"b": 1}),
        "c": [Data(data="text"), 2],
    }

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {
        "a": {"b": 1},
        "c": ["text", 2],
    }


def test_list_recursive_conversion(tracer):
    value = [
        Data(data={"x": 1}),
        Data(data="y"),
    ]

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == [{"x": 1}, "y"]


def test_float_nan_conversion(tracer):
    value = float("nan")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == "NaN"


def test_float_inf_conversion(tracer):
    value = float("inf")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == "NaN"


def test_none_type_conversion(tracer):
    value = None

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == "None"


def test_generator_conversion(tracer):
    def gen():
        yield 1

    value = gen()

    result = tracer._convert_to_arize_phoenix_type(value)

    assert isinstance(result, str)


def test_plain_dict_unchanged(tracer):
    value = {"a": 1, "b": 2}

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == value


def test_plain_list_unchanged(tracer):
    value = [1, 2, 3]

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == value
