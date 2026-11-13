import json

import numpy as np
import pytest
from lfx.helpers.data import safe_convert
from lfx.schema.data import Data


def _parse_json_block(output: str):
    assert output.startswith("```json\n")
    assert output.endswith("\n```")
    return json.loads(output.removeprefix("```json\n").removesuffix("\n```"))


def test_should_serialize_mmr_scores_as_plain_numbers_when_values_are_numpy_float64():
    data = Data(data={"text": "x", "similarity_score": np.float64(0.8), "mmr_score": np.float64(-0.37)})

    parsed = _parse_json_block(safe_convert(data))

    assert parsed == {"text": "x", "similarity_score": 0.8, "mmr_score": -0.37}


def test_should_serialize_cassandra_mmr_document_metadata_when_links_is_empty_set():
    data = Data(
        data={
            "links": set(),
            "similarity_score": np.float64(0.8164966156209729),
            "mmr_score": np.float64(0.40824830781048643),
            "text": "cassandra graph traversal a1",
        }
    )

    parsed = _parse_json_block(safe_convert(data))

    assert parsed == {
        "links": [],
        "similarity_score": 0.8164966156209729,
        "mmr_score": 0.40824830781048643,
        "text": "cassandra graph traversal a1",
    }


def test_should_serialize_numpy_int_bool_and_ndarray_when_nested_in_dicts_and_lists():
    data = Data(
        data={
            "text": "x",
            "meta": {"rank": np.int64(3), "kept": np.True_, "half": np.float32(0.5)},
            "scores": [np.int32(1), {"vector": np.array([[1.5, 2.0], [3.0, 4.5]])}],
            "ids": np.array([7, 8], dtype=np.int64),
        }
    )

    parsed = _parse_json_block(safe_convert(data))

    assert parsed == {
        "text": "x",
        "meta": {"rank": 3, "kept": True, "half": 0.5},
        "scores": [1, {"vector": [[1.5, 2.0], [3.0, 4.5]]}],
        "ids": [7, 8],
    }
    assert type(parsed["meta"]["kept"]) is bool
    assert type(parsed["meta"]["rank"]) is int


def test_should_serialize_empty_ndarray_as_empty_list():
    parsed = _parse_json_block(safe_convert(Data(data={"text": "x", "vector": np.array([])})))

    assert parsed == {"text": "x", "vector": []}


def test_should_keep_plain_python_output_unchanged():
    data = Data(data={"text": "hello", "count": 3, "ratio": 0.25, "nested": {"ok": True, "items": [1, "a", None]}})

    output = safe_convert(data)

    assert output == (
        "```json\n"
        "{\n"
        '  "text": "hello",\n'
        '  "count": 3,\n'
        '  "ratio": 0.25,\n'
        '  "nested": {\n'
        '    "ok": true,\n'
        '    "items": [\n'
        "      1,\n"
        '      "a",\n'
        "      null\n"
        "    ]\n"
        "  }\n"
        "}\n"
        "```"
    )


def test_should_raise_conversion_error_when_value_is_unserializable():
    with pytest.raises(ValueError, match=r"^Error converting data: "):
        safe_convert(Data(data={"text": "x", "bad": object()}))


def test_should_raise_conversion_error_when_object_ndarray_holds_unserializable_value():
    with pytest.raises(ValueError, match=r"^Error converting data: "):
        safe_convert(Data(data={"text": "x", "bad": np.array([object()], dtype=object)}))
