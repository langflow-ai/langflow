import uuid
from datetime import datetime, timezone

import pytest
from langflow.services.database.models.transactions.model import TransactionBase


def test_serialize_inputs_excludes_code_key():
    """Test that the code key is excluded from inputs when serializing."""
    # Create a TransactionBase object with inputs containing a code key
    transaction = TransactionBase(
        timestamp=datetime.now(timezone.utc),
        vertex_id="test-vertex",
        target_id="test-target",
        inputs={"param1": "value1", "param2": "value2", "code": "print('Hello, world!')"},
        outputs={"result": "success"},
        status="completed",
        flow_id=uuid.uuid4(),
    )

    # Get the serialized inputs
    serialized_inputs = transaction.serialize_inputs(transaction.inputs)

    # Verify that the code key is excluded
    assert "code" not in serialized_inputs
    assert "param1" in serialized_inputs
    assert "param2" in serialized_inputs
    assert serialized_inputs["param1"] == "value1"
    assert serialized_inputs["param2"] == "value2"


def test_serialize_inputs_handles_none():
    """Test that the serialize_inputs method handles None inputs."""
    # Create a TransactionBase object with None inputs
    transaction = TransactionBase(
        timestamp=datetime.now(timezone.utc),
        vertex_id="test-vertex",
        target_id="test-target",
        inputs=None,
        outputs={"result": "success"},
        status="completed",
        flow_id=uuid.uuid4(),
    )

    # Get the serialized inputs
    serialized_inputs = transaction.serialize_inputs(transaction.inputs)

    # Verify that None is returned
    assert serialized_inputs is None


def test_serialize_inputs_handles_non_dict():
    """Test that the serialize_inputs method handles non-dict inputs."""
    # Create a TransactionBase object with valid inputs
    transaction = TransactionBase(
        timestamp=datetime.now(timezone.utc),
        vertex_id="test-vertex",
        target_id="test-target",
        inputs={},  # Empty dict is valid
        outputs={"result": "success"},
        status="completed",
        flow_id=uuid.uuid4(),
    )

    # Call serialize_inputs directly with a non-dict value
    serialized_inputs = transaction.serialize_inputs("not a dict")

    # Verify that the input is returned as is
    assert serialized_inputs == "not a dict"


def test_serialize_inputs_handles_empty_dict():
    """Test that the serialize_inputs method handles empty dict inputs."""
    # Create a TransactionBase object with empty dict inputs
    transaction = TransactionBase(
        timestamp=datetime.now(timezone.utc),
        vertex_id="test-vertex",
        target_id="test-target",
        inputs={},
        outputs={"result": "success"},
        status="completed",
        flow_id=uuid.uuid4(),
    )

    # Get the serialized inputs
    serialized_inputs = transaction.serialize_inputs(transaction.inputs)

    # Verify that an empty dict is returned
    assert serialized_inputs == {}


@pytest.mark.asyncio
async def test_code_key_not_saved_to_database():
    """Test that the code key is not saved to the database."""
    # Create input data with a code key
    input_data = {"param1": "value1", "param2": "value2", "code": "print('Hello, world!')"}

    # Create a transaction with inputs containing a code key
    transaction = TransactionBase(
        timestamp=datetime.now(timezone.utc),
        vertex_id="test-vertex",
        target_id="test-target",
        inputs=input_data,
        outputs={"result": "success"},
        status="completed",
        flow_id=uuid.uuid4(),
    )

    # Verify that the code key is removed during transaction creation
    assert transaction.inputs is not None
    assert "code" not in transaction.inputs
    assert "param1" in transaction.inputs
    assert "param2" in transaction.inputs

    # Verify that the code key is excluded when serializing
    serialized_inputs = transaction.serialize_inputs(transaction.inputs)
    assert "code" not in serialized_inputs
    assert "param1" in serialized_inputs
    assert "param2" in serialized_inputs


# Made with Bob
