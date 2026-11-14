import json

import numpy as np
import pytest
from langflow.helpers.data import safe_convert
from lfx.schema.data import Data


def test_should_serialize_cassandra_mmr_document_metadata_when_scores_are_numpy_float64():
    data = Data(
        data={
            "links": set(),
            "similarity_score": np.float64(0.8164966156209729),
            "mmr_score": np.float64(0.40824830781048643),
            "text": "cassandra graph traversal a1",
        }
    )

    output = safe_convert(data)

    assert output.startswith("```json\n")
    assert output.endswith("\n```")
    assert json.loads(output.removeprefix("```json\n").removesuffix("\n```")) == {
        "links": [],
        "similarity_score": 0.8164966156209729,
        "mmr_score": 0.40824830781048643,
        "text": "cassandra graph traversal a1",
    }


def test_should_serialize_nested_numpy_int_bool_and_ndarray():
    data = Data(data={"meta": {"rank": np.int64(3), "kept": np.True_}, "ids": [np.array([7, 8])]})

    parsed = json.loads(safe_convert(data).removeprefix("```json\n").removesuffix("\n```"))

    assert parsed == {"meta": {"rank": 3, "kept": True}, "ids": [[7, 8]]}


def test_should_keep_plain_python_output_unchanged():
    output = safe_convert(Data(data={"text": "hello", "count": 3, "items": [1, None]}))

    assert output == ('```json\n{\n  "text": "hello",\n  "count": 3,\n  "items": [\n    1,\n    null\n  ]\n}\n```')


def test_should_raise_conversion_error_when_value_is_unserializable():
    with pytest.raises(ValueError, match=r"^Error converting data: "):
        safe_convert(Data(data={"text": "x", "bad": object()}))
