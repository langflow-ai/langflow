"""Tests for ComponentInputsPayload splitting logic."""

import orjson
from hypothesis import given
from hypothesis import strategies as st
from langflow.services.telemetry.schema import MAX_TELEMETRY_PAYLOAD_SIZE, ComponentInputsPayload


def test_chunk_fields_exist():
    """Test that chunk_index and total_chunks fields exist on payload."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "value1"},
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
        component_inputs={"input1": "value1"},
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
        component_inputs={"input1": "value1"},
    )

    assert payload.chunk_index is None
    assert payload.total_chunks is None


def test_calculate_payload_size_returns_serialized_json_bytes():
    """Payload size is the UTF-8 byte length of the JSON sent to Segment."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "áéíóú"},
    )

    serialized = orjson.dumps(payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True))

    assert payload._calculate_payload_size() == len(serialized)


def test_calculate_payload_size_accounts_for_encoding():
    """Test that payload size accounts for special character encoding."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "value with spaces & special=chars"},
    )

    size = payload._calculate_payload_size()
    # Size should be larger than raw dict due to JSON serialization and JSON encoding
    import orjson

    serialized_size = len(orjson.dumps(payload.component_inputs).decode("utf-8"))
    assert size > serialized_size


def test_calculate_payload_size_includes_all_fields():
    """Test that payload size includes all payload fields."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "value1"},
        chunk_index=0,
        total_chunks=1,
    )

    size = payload._calculate_payload_size()
    # Size should include all serialized payload fields
    assert size > 100  # Reasonable minimum for all fields


def test_split_if_needed_returns_list():
    """Test that split_if_needed returns a list of payloads."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "value1"},
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)
    assert isinstance(result, list)
    assert len(result) > 0


def test_split_if_needed_no_split_returns_single_payload():
    """Test that small payload returns single payload unchanged."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "value1"},
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)
    assert len(result) == 1
    assert result[0].component_run_id == "test-run-id"
    assert result[0].component_inputs == {"input1": "value1"}


def test_split_if_needed_no_split_has_no_chunk_metadata():
    """Test that single payload has None for chunk fields."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={"input1": "value1"},
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)
    assert result[0].chunk_index is None
    assert result[0].total_chunks is None


def test_split_if_needed_splits_large_payload():
    """Test that large payload is split into multiple chunks."""
    large_inputs = {f"input_{i}": "x" * 100 for i in range(500)}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=large_inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)
    assert len(result) > 1  # Should be split


def test_split_preserves_fixed_fields():
    """Test that all chunks have identical fixed fields."""
    large_inputs = {f"input_{i}": "x" * 100 for i in range(50)}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=large_inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    for chunk in result:
        assert chunk.component_run_id == "test-run-id"
        assert chunk.component_id == "test-comp-id"
        assert chunk.component_name == "TestComponent"


def test_split_chunk_metadata_correct():
    """Test that chunk_index and total_chunks are correct."""
    large_inputs = {f"input_{i}": "x" * 100 for i in range(500)}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=large_inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # Check chunk indices are sequential
    for i, chunk in enumerate(result):
        assert chunk.chunk_index == i
        assert chunk.total_chunks == len(result)


def test_split_preserves_all_data():
    """Test that merging all chunks recreates original data."""
    large_inputs = {f"input_{i}": f"value_{i}" for i in range(50)}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=large_inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # Merge all chunk inputs
    merged_inputs = {}
    for chunk in result:
        merged_inputs.update(chunk.component_inputs)

    assert merged_inputs == large_inputs


def test_split_chunks_respect_max_size():
    """Test that all chunks respect max payload size."""
    large_inputs = {f"input_{i}": "x" * 100 for i in range(50)}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=large_inputs,
    )

    max_size = MAX_TELEMETRY_PAYLOAD_SIZE
    result = payload.split_if_needed(max_payload_size=max_size)

    for chunk in result:
        chunk_size = chunk._calculate_payload_size()
        assert chunk_size <= max_size


def test_split_truncates_oversized_single_field():
    """Test that single field exceeding max size gets truncated."""
    oversized_value = "x" * (MAX_TELEMETRY_PAYLOAD_SIZE * 2)
    inputs = {"large_field": oversized_value}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # Should return single payload with truncated value
    assert len(result) == 1
    chunk_inputs = result[0].component_inputs
    assert "large_field" in chunk_inputs
    assert len(chunk_inputs["large_field"]) < len(oversized_value)
    assert "...[truncated]" in chunk_inputs["large_field"]

    # Verify the chunk respects max size
    chunk_size = result[0]._calculate_payload_size()
    assert chunk_size <= MAX_TELEMETRY_PAYLOAD_SIZE


def test_split_handles_empty_inputs():
    """Test that empty inputs dict returns single payload."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs={},
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)
    assert len(result) == 1
    assert result[0].component_inputs == {}


def test_split_truncates_oversized_non_string_field():
    """Test that non-string oversized field gets converted to string and truncated."""
    # Create input with single non-string field that's too large
    oversized_list = [{"key": "value" * 100} for _ in range(100)]
    inputs = {"large_list": oversized_list}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # Should return single payload with truncated value
    assert len(result) == 1
    chunk_inputs = result[0].component_inputs
    assert "large_list" in chunk_inputs

    # Value should be converted to string and truncated
    assert isinstance(chunk_inputs["large_list"], str)
    assert "...[truncated]" in chunk_inputs["large_list"]

    # Verify the chunk respects max size
    chunk_size = result[0]._calculate_payload_size()
    assert chunk_size <= MAX_TELEMETRY_PAYLOAD_SIZE


def test_split_truncates_oversized_field_in_multi_field_payload():
    """Test that oversized field gets truncated when splitting multi-field payload."""
    # Create inputs with normal fields and one oversized field
    inputs = {
        "normal1": "value1",
        "normal2": "value2",
        "huge_field": "x" * (MAX_TELEMETRY_PAYLOAD_SIZE * 2),
        "normal3": "value3",
    }

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # Should be split into multiple chunks
    assert len(result) > 1

    # All chunks must respect max size
    for chunk in result:
        chunk_size = chunk._calculate_payload_size()
        assert chunk_size <= MAX_TELEMETRY_PAYLOAD_SIZE

    # The huge_field should be truncated
    huge_field_found = False
    for chunk in result:
        if "huge_field" in chunk.component_inputs:
            huge_field_found = True
            assert "...[truncated]" in chunk.component_inputs["huge_field"]
            assert len(chunk.component_inputs["huge_field"]) < MAX_TELEMETRY_PAYLOAD_SIZE * 2

    assert huge_field_found, "huge_field should be in one of the chunks"


# Hypothesis property-based tests


@given(st.dictionaries(st.text(min_size=1, max_size=50), st.text(max_size=200), min_size=1))
def test_property_split_never_exceeds_max_size(inputs_dict):
    """Property: Every chunk payload must be <= max_payload_size."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs_dict,
    )

    max_size = MAX_TELEMETRY_PAYLOAD_SIZE
    result = payload.split_if_needed(max_payload_size=max_size)

    for chunk in result:
        chunk_size = chunk._calculate_payload_size()
        assert chunk_size <= max_size, f"Chunk size {chunk_size} exceeds max {max_size}"


@given(st.dictionaries(st.text(min_size=1, max_size=50), st.text(max_size=200), min_size=1))
def test_property_split_preserves_all_data(inputs_dict):
    """Property: Merging all chunks recreates original inputs (unless truncated)."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs_dict,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # Merge all chunk inputs
    merged_inputs = {}
    has_truncation = False
    for chunk in result:
        chunk_inputs = chunk.component_inputs
        for key, value in chunk_inputs.items():
            if isinstance(value, str) and "...[truncated]" in value:
                has_truncation = True
            merged_inputs[key] = value

    # If no truncation, data should be preserved
    if not has_truncation:
        assert merged_inputs == inputs_dict


@given(
    st.dictionaries(st.text(min_size=1, max_size=50), st.text(max_size=200), min_size=1),
    st.text(min_size=1, max_size=100),
    st.text(min_size=1, max_size=100),
    st.text(min_size=1, max_size=100),
)
def test_property_fixed_fields_identical_across_chunks(inputs_dict, run_id, comp_id, comp_name):
    """Property: All chunks have identical fixed fields."""
    payload = ComponentInputsPayload(
        component_run_id=run_id,
        component_id=comp_id,
        component_name=comp_name,
        component_inputs=inputs_dict,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    for chunk in result:
        assert chunk.component_run_id == run_id
        assert chunk.component_id == comp_id
        assert chunk.component_name == comp_name


@given(st.dictionaries(st.text(min_size=1, max_size=50), st.text(max_size=200), min_size=1))
def test_property_chunk_indices_sequential(inputs_dict):
    """Property: chunk_index goes 0,1,2... and total_chunks is correct."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs_dict,
    )

    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    if len(result) == 1:
        # Single payload should have None chunk metadata
        assert result[0].chunk_index is None
        assert result[0].total_chunks is None
    else:
        # Multiple chunks should have sequential indices
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(result)


@given(
    st.dictionaries(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\x00"),
        ),
        st.text(
            max_size=200,
            alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\x00"),
        ),
        min_size=1,
    )
)
def test_property_handles_special_characters(inputs_dict):
    """Property: JSON encoding doesn't break splitting logic."""
    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=inputs_dict,
    )

    # Should not raise any exceptions
    result = payload.split_if_needed(max_payload_size=MAX_TELEMETRY_PAYLOAD_SIZE)

    # All chunks should be valid
    assert len(result) > 0
    for chunk in result:
        assert chunk.component_run_id == "test-run-id"
        assert isinstance(chunk.component_inputs, dict)
