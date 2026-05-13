import pytest
from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer
from lfx.schema.data import Data


@pytest.fixture
def tracer():
    return ArizePhoenixTracer.__new__(ArizePhoenixTracer)


def test_data_dict_conversion(tracer):
    value = Data(data={"a": 1, "b": "x"})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"a": 1, "b": "x"}


def test_data_list_conversion(tracer):
    value = Data.model_construct(data=[1, Data(data={"x": 2})], text_key="text", default_value="")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == [1, {"x": 2}]


def test_data_text_payload_preserved(tracer):
    value = Data(data={"text": "hello"})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"text": "hello"}


def test_data_nested_structure(tracer):
    value = Data(data={"nested": [1, Data(data={"x": float("inf")})]})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"nested": [1, {"x": "NaN"}]}


def test_data_none(tracer):
    value = Data(data=None)

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {}


def test_dict_recursive_conversion(tracer):
    value = {
        "a": Data(data={"b": 1}),
        "c": [Data(data={"text": "text"}), 2],
    }

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {
        "a": {"b": 1},
        "c": [{"text": "text"}, 2],
    }


def test_list_recursive_conversion(tracer):
    value = [
        Data(data={"x": 1}),
        Data(data={"text": "y"}),
    ]

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == [{"x": 1}, {"text": "y"}]


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
