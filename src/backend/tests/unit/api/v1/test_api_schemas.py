from datetime import datetime, timezone

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st
from langflow.api.v1.schemas import ResultDataResponse, VertexBuildResponse
from langflow.schema.schema import OutputValue
from langflow.serialization import serialize
from langflow.services.tracing.schema import Log
from pydantic import BaseModel

# Use a smaller test size for hypothesis
TEST_TEXT_LENGTH = 50


class SampleBaseModel(BaseModel):
    name: str
    value: int


@given(st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2))
@settings(max_examples=10)
def test_result_data_response_truncation(long_string):
    """Test that ResultDataResponse properly truncates long strings."""
    response = ResultDataResponse(
        results={"long_text": long_string},
        message={"text": long_string},
    )

    response.serialize_model()
    truncated = serialize(long_string, max_length=TEST_TEXT_LENGTH)
    assert len(truncated) <= TEST_TEXT_LENGTH + len("...")
    assert "..." in truncated


@given(
    st.uuids(),
    st.datetimes(timezones=st.just(timezone.utc)),
    st.decimals(min_value="-1e6", max_value="1e6"),
    st.text(min_size=1),
    st.integers(),
)
@settings(max_examples=10)
def test_result_data_response_special_types(uuid, dt, decimal, name, value):
    """Test that ResultDataResponse properly handles special data types."""
    test_model = SampleBaseModel(name=name, value=value)

    response = ResultDataResponse(
        results={
            "uuid": uuid,
            "datetime": dt,
            "decimal": decimal,
            "model": test_model,
        }
    )

    serialized = response.serialize_model()
    assert serialized["results"]["uuid"] == str(uuid)
    # Compare timezone-aware datetimes
    assert datetime.fromisoformat(serialized["results"]["datetime"]).astimezone(timezone.utc) == dt
    assert isinstance(serialized["results"]["decimal"], float)
    assert serialized["results"]["model"] == {"name": name, "value": value}


@given(
    st.lists(st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2), min_size=1, max_size=2),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2),
        min_size=1,
        max_size=2,
    ),
)
@settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example])
def test_result_data_response_nested_structures(long_list, long_dict):
    """Test that ResultDataResponse handles nested structures correctly."""
    nested_data = {
        "list": long_list,
        "dict": long_dict,
    }

    ResultDataResponse(results=nested_data)
    serialized = serialize(nested_data, max_length=TEST_TEXT_LENGTH)

    # Check list items
    for item in serialized["list"]:
        assert len(item) <= TEST_TEXT_LENGTH + len("...")
        if len(item) > TEST_TEXT_LENGTH:
            assert "..." in item

    # Check dict values
    for val in serialized["dict"].values():
        assert len(val) <= TEST_TEXT_LENGTH + len("...")
        if len(val) > TEST_TEXT_LENGTH:
            assert "..." in val


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=5),
        values=st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2),
        min_size=1,
        max_size=2,
    ),
)
@settings(max_examples=10)
@example(
    outputs_dict={"0": "000000000000000000000000000000000000000000000000000"},
).via("discovered failure")
@example(
    outputs_dict={"0": "000000000000000000000000000000000000000000000000000000000000000000"},
).via("discovered failure")
def test_result_data_response_outputs(outputs_dict):
    """Test that ResultDataResponse properly handles and truncates outputs."""
    # Create OutputValue objects with potentially long messages
    outputs = {key: OutputValue(type="text", message=value) for key, value in outputs_dict.items()}

    response = ResultDataResponse(outputs=outputs)
    serialized = serialize(response, max_length=TEST_TEXT_LENGTH)

    # Check outputs are properly serialized and truncated
    for key, value in outputs_dict.items():
        assert key in serialized["outputs"]
        serialized_output = serialized["outputs"][key]
        assert serialized_output["type"] == "text"

        # Check message truncation
        message = serialized_output["message"]
        assert len(message) <= TEST_TEXT_LENGTH + len("..."), f"Message length: {len(message)}"
        if len(value) > TEST_TEXT_LENGTH:
            assert "..." in message
            assert message.startswith(value[:TEST_TEXT_LENGTH])
        else:
            assert message == value


@given(
    st.lists(
        st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2),
        min_size=1,
        max_size=3,
    ),
)
@settings(max_examples=10)
@example(
    log_messages=["000000000000000000000000000000000000000000000000000"],
).via("discovered failure")
def test_result_data_response_logs(log_messages):
    """Test that ResultDataResponse properly handles and truncates logs."""
    # Create logs with long messages
    logs = {
        "test_node": [
            Log(
                message=msg,
                name="test_log",
                type="test",
            )
            for msg in log_messages
        ]
    }

    response = ResultDataResponse(logs=logs)
    serialized = serialize(response, max_length=TEST_TEXT_LENGTH)

    # Check logs are properly serialized and truncated
    assert "test_node" in serialized["logs"]
    serialized_logs = serialized["logs"]["test_node"]

    for i, log_msg in enumerate(log_messages):
        serialized_log = serialized_logs[i]
        assert serialized_log["name"] == "test_log"
        assert serialized_log["type"] == "test"

        # Check message truncation
        message = serialized_log["message"]
        assert len(message) <= TEST_TEXT_LENGTH + len("...")
        if len(log_msg) > TEST_TEXT_LENGTH:
            assert "..." in message
            assert message.startswith(log_msg[:TEST_TEXT_LENGTH])
        else:
            assert message == log_msg


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=5),
        values=st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2),
        min_size=1,
        max_size=2,
    ),
    st.lists(
        st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2),
        min_size=1,
        max_size=3,
    ),
)
@settings(max_examples=10)
@example(
    outputs_dict={"0": "000000000000000000000000000000000000000000000000000000000000000000"},
    log_messages=["000000000000000000000000000000000000000000000000000"],
).via("discovered failure")
@example(
    outputs_dict={"0": "000000000000000000000000000000000000000000000000000"},
    log_messages=["000000000000000000000000000000000000000000000000000"],
).via("discovered failure")
def test_result_data_response_combined_fields(outputs_dict, log_messages):
    """Test that ResultDataResponse properly handles all fields together."""
    # Create OutputValue objects with potentially long messages
    outputs = {key: OutputValue(type="text", message=value) for key, value in outputs_dict.items()}

    # Create logs with long messages
    logs = {
        "test_node": [
            Log(
                message=msg,
                name="test_log",
                type="test",
            )
            for msg in log_messages
        ]
    }

    response = ResultDataResponse(
        outputs=outputs,
        logs=logs,
        results={"test": "value"},
        message={"text": "test"},
        artifacts={"file": "test.txt"},
    )
    serialized = serialize(response, max_length=TEST_TEXT_LENGTH)

    # Check all fields are present
    assert "outputs" in serialized
    assert "logs" in serialized
    assert "results" in serialized
    assert "message" in serialized
    assert "artifacts" in serialized

    # Check outputs truncation
    for key, value in outputs_dict.items():
        assert key in serialized["outputs"]
        serialized_output = serialized["outputs"][key]
        assert serialized_output["type"] == "text"

        # Check message truncation
        message = serialized_output["message"]
        if len(value) > TEST_TEXT_LENGTH:
            assert len(message) <= TEST_TEXT_LENGTH + len("...")
            assert "..." in message
        else:
            assert message == value

    # Check logs truncation
    assert "test_node" in serialized["logs"]
    serialized_logs = serialized["logs"]["test_node"]

    for i, log_msg in enumerate(log_messages):
        serialized_log = serialized_logs[i]
        assert serialized_log["name"] == "test_log"
        assert serialized_log["type"] == "test"

        # Check message truncation
        message = serialized_log["message"]
        if len(log_msg) > TEST_TEXT_LENGTH:
            assert len(message) <= TEST_TEXT_LENGTH + len("...")
            assert "..." in message
        else:
            assert message == log_msg


@given(
    st.text(min_size=1),  # build_id
    st.lists(st.text()),  # logs
    st.text(min_size=1),  # message
)
@settings(max_examples=10)
def test_vertex_build_response_serialization(build_id, log_messages, test_message):
    """Test that VertexBuildResponse properly serializes its data field."""
    logs = [Log(message=msg, name="test_log", type="test") for msg in log_messages]

    result_data = ResultDataResponse(
        results={"test": test_message},
        message={"text": test_message},
        logs={"node1": logs},
    )

    response = VertexBuildResponse(
        id=build_id,
        valid=True,
        data=result_data,
    )

    serialized = response.model_dump()
    assert serialized["id"] == build_id
    assert serialized["valid"] is True
    assert isinstance(serialized["data"], dict)
    assert serialized["data"]["results"]["test"] == test_message


@given(st.text(min_size=TEST_TEXT_LENGTH + 1, max_size=TEST_TEXT_LENGTH * 2))
@settings(max_examples=10)
def test_vertex_build_response_with_long_data(long_string):
    """Test that VertexBuildResponse properly handles long data in its data field."""
    result_data = ResultDataResponse(
        results={"long_text": long_string},
        message={"text": long_string},
    )

    response = VertexBuildResponse(
        id="test-id",
        valid=True,
        data=result_data,
    )

    response.model_dump()
    truncated = serialize(long_string, max_length=TEST_TEXT_LENGTH)
    assert len(truncated) <= TEST_TEXT_LENGTH + len("...")
    assert "..." in truncated
