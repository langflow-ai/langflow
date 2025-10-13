"""Tests for ComponentInputsPayload splitting logic."""

from langflow.services.telemetry.schema import ComponentInputsPayload


def test_chunk_fields_exist():
    """Test that chunk_index and total_chunks fields exist on payload."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs='{"input1": "value1"}',
        chunk_index=0,
        total_chunks=1,
    )

    assert payload.chunk_index == 0
    assert payload.total_chunks == 1


def test_chunk_fields_serialize_with_aliases():
    """Test that chunk fields use camelCase aliases."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs='{"input1": "value1"}',
        chunk_index=2,
        total_chunks=5,
    )

    data = payload.model_dump(by_alias=True)
    assert data["chunkIndex"] == 2
    assert data["totalChunks"] == 5


def test_chunk_fields_optional_default_none():
    """Test that chunk fields default to None when not provided."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs='{"input1": "value1"}',
    )

    assert payload.chunk_index is None
    assert payload.total_chunks is None
