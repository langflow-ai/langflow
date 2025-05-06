import pytest
from langflow.api.v1.schemas import VertexBuildResponse
from langflow.serialization.constants import MAX_ITEMS_LENGTH

expected_keys_vertex_build_response = {
    "id",
    "inactivated_vertices",
    "next_vertices_ids",
    "top_level_vertices",
    "valid",
    "params",
    "data",
    "timestamp",
}
expected_keys_data = {
    "results",
    "outputs",
    "logs",
    "message",
    "artifacts",
    "timedelta",
    "duration",
    "used_frozen_result",
}
expected_keys_outputs = {"message", "type"}


def assert_vertex_response_structure(result):
    assert set(result.keys()).issuperset(expected_keys_vertex_build_response)
    assert set(result["data"].keys()).issuperset(expected_keys_data)
    assert set(result["data"]["outputs"]["dataframe"].keys()).issuperset(expected_keys_outputs)


def test_vertex_response_structure_without_truncate():
    message = [{"key": 1, "value": 1}]
    output_value = {"message": message, "type": "bar"}
    data = {
        "data": {"outputs": {"dataframe": output_value}, "type": "foo"},
        "valid": True,
    }

    result = VertexBuildResponse(**data).model_dump()

    assert_vertex_response_structure(result)
    assert len(result["data"]["outputs"]["dataframe"]["message"]) == len(message)


def test_vertex_response_structure_when_truncate_applies():
    message = [{"key": i, "value": i} for i in range(MAX_ITEMS_LENGTH + 5000)]
    output_value = {"message": message, "type": "bar"}
    data = {
        "data": {"outputs": {"dataframe": output_value}, "type": "foo"},
        "valid": True,
    }

    result = VertexBuildResponse(**data).model_dump()

    assert_vertex_response_structure(result)
    assert len(result["data"]["outputs"]["dataframe"]["message"]) == MAX_ITEMS_LENGTH + 1


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, 0),
        (8, 8),
        (MAX_ITEMS_LENGTH, MAX_ITEMS_LENGTH),
        (MAX_ITEMS_LENGTH + 1000, MAX_ITEMS_LENGTH + 1),
        (MAX_ITEMS_LENGTH + 2000, MAX_ITEMS_LENGTH + 1),
        (MAX_ITEMS_LENGTH + 3000, MAX_ITEMS_LENGTH + 1),
    ],
)
def test_vertex_response_truncation_behavior(size, expected):
    message = [{"key": i, "value": i} for i in range(size)]
    output_value = {"message": message, "type": "bar"}
    data = {
        "data": {"outputs": {"dataframe": output_value}, "type": "foo"},
        "valid": True,
    }

    result = VertexBuildResponse(**data).model_dump()
    assert len(result["data"]["outputs"]["dataframe"]["message"]) == expected
