"""Unit tests for session_metadata functionality in Message and MessageTable."""

from uuid import uuid4

import pytest
from langflow.memory import aadd_messages, aget_messages, astore_message
from langflow.schema.message import Message
from langflow.services.database.models.message import MessageCreate, MessageRead
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture
def sample_session_metadata():
    """Sample session metadata for testing."""
    return {
        "tenant_id": "tenant-123",
        "user_id": "user-456",
        "region": "us-east-1",
        "retention_profile": "standard",
        "data_flags": {"pii": True, "sensitive": False},
        "custom_fields": {"department": "engineering", "project": "langflow"},
    }


@pytest.fixture
def minimal_session_metadata():
    """Minimal session metadata for testing."""
    return {
        "tenant_id": "tenant-789",
        "user_id": "user-012",
    }


@pytest.mark.usefixtures("client")
async def test_message_with_session_metadata(sample_session_metadata):
    """Test creating a Message with session_metadata."""
    message = Message(
        text="Test message with metadata",
        sender="User",
        sender_name="Test User",
        session_id="test_session_1",
        session_metadata=sample_session_metadata,
    )

    assert message.session_metadata == sample_session_metadata
    assert message.session_metadata["tenant_id"] == "tenant-123"
    assert message.session_metadata["user_id"] == "user-456"
    assert message.session_metadata["region"] == "us-east-1"


@pytest.mark.usefixtures("client")
async def test_message_without_session_metadata():
    """Test creating a Message without session_metadata (backward compatibility)."""
    message = Message(
        text="Test message without metadata",
        sender="User",
        sender_name="Test User",
        session_id="test_session_2",
    )

    assert message.session_metadata is None


@pytest.mark.usefixtures("client")
async def test_store_message_with_session_metadata(sample_session_metadata):
    """Test storing a message with session_metadata."""
    session_id = f"stored_session_{uuid4()}"
    message = Message(
        text="Stored message with metadata",
        sender="User",
        sender_name="Test User",
        session_id=session_id,
        session_metadata=sample_session_metadata,
    )

    await astore_message(message)

    # Retrieve and verify
    stored_messages = await aget_messages(sender="User", session_id=session_id)
    assert len(stored_messages) == 1
    assert stored_messages[0].text == "Stored message with metadata"
    assert stored_messages[0].session_metadata == sample_session_metadata


@pytest.mark.usefixtures("client")
async def test_store_message_without_session_metadata():
    """Test storing a message without session_metadata (backward compatibility)."""
    session_id = f"stored_session_{uuid4()}"
    message = Message(
        text="Stored message without metadata",
        sender="User",
        sender_name="Test User",
        session_id=session_id,
    )

    await astore_message(message)

    # Retrieve and verify
    stored_messages = await aget_messages(sender="User", session_id=session_id)
    assert len(stored_messages) == 1
    assert stored_messages[0].text == "Stored message without metadata"
    assert stored_messages[0].session_metadata is None


@pytest.mark.usefixtures("client")
async def test_add_messages_with_session_metadata(sample_session_metadata, minimal_session_metadata):
    """Test adding multiple messages with different session_metadata."""
    session_id = f"batch_session_{uuid4()}"
    messages = [
        Message(
            text="Message 1 with full metadata",
            sender="User",
            sender_name="User 1",
            session_id=session_id,
            session_metadata=sample_session_metadata,
        ),
        Message(
            text="Message 2 with minimal metadata",
            sender="User",
            sender_name="User 2",
            session_id=session_id,
            session_metadata=minimal_session_metadata,
        ),
        Message(
            text="Message 3 without metadata",
            sender="User",
            sender_name="User 3",
            session_id=session_id,
        ),
    ]

    added_messages = await aadd_messages(messages)

    assert len(added_messages) == 3
    assert added_messages[0].session_metadata == sample_session_metadata
    assert added_messages[1].session_metadata == minimal_session_metadata
    assert added_messages[2].session_metadata is None


@pytest.mark.usefixtures("client")
async def test_messagetable_from_message_with_metadata(sample_session_metadata):
    """Test MessageTable.from_message() extracts session_metadata correctly."""
    message = Message(
        text="Test message",
        sender="User",
        sender_name="Test User",
        session_id="test_session_3",
        session_metadata=sample_session_metadata,
    )

    message_table = MessageTable.from_message(message, flow_id=uuid4())

    assert message_table.session_metadata == sample_session_metadata
    assert message_table.session_metadata["tenant_id"] == "tenant-123"
    assert message_table.session_metadata["user_id"] == "user-456"


@pytest.mark.usefixtures("client")
async def test_messagetable_from_message_without_metadata():
    """Test MessageTable.from_message() handles missing session_metadata."""
    message = Message(
        text="Test message",
        sender="User",
        sender_name="Test User",
        session_id="test_session_4",
    )

    message_table = MessageTable.from_message(message, flow_id=uuid4())

    assert message_table.session_metadata is None


@pytest.mark.usefixtures("client")
async def test_messagecreate_with_session_metadata(sample_session_metadata):
    """Test MessageCreate schema with session_metadata."""
    message_create = MessageCreate(
        text="Test message",
        sender="User",
        sender_name="Test User",
        session_id="test_session_5",
        session_metadata=sample_session_metadata,
    )

    assert message_create.session_metadata == sample_session_metadata


@pytest.mark.usefixtures("client")
async def test_messagecreate_without_session_metadata():
    """Test MessageCreate schema without session_metadata."""
    message_create = MessageCreate(
        text="Test message",
        sender="User",
        sender_name="Test User",
        session_id="test_session_6",
    )

    assert message_create.session_metadata is None


@pytest.mark.usefixtures("client")
async def test_messageread_with_session_metadata(sample_session_metadata):
    """Test MessageRead schema includes session_metadata."""
    async with session_scope() as session:
        message_create = MessageCreate(
            text="Test message",
            sender="User",
            sender_name="Test User",
            session_id=f"test_session_{uuid4()}",
            session_metadata=sample_session_metadata,
        )
        message_table = MessageTable.model_validate(message_create, from_attributes=True)
        session.add(message_table)
        await session.commit()
        await session.refresh(message_table)

        message_read = MessageRead.model_validate(message_table, from_attributes=True)

        assert message_read.session_metadata == sample_session_metadata


@pytest.mark.usefixtures("client")
async def test_session_metadata_persistence_and_retrieval(sample_session_metadata):
    """Test full cycle: create, store, retrieve, and verify session_metadata."""
    session_id = f"full_cycle_session_{uuid4()}"

    # Create and store
    message = Message(
        text="Full cycle test message",
        sender="User",
        sender_name="Test User",
        session_id=session_id,
        session_metadata=sample_session_metadata,
    )
    await astore_message(message)

    # Retrieve
    retrieved_messages = await aget_messages(sender="User", session_id=session_id)

    # Verify
    assert len(retrieved_messages) == 1
    retrieved = retrieved_messages[0]
    assert retrieved.text == "Full cycle test message"
    assert retrieved.session_metadata is not None
    assert retrieved.session_metadata["tenant_id"] == "tenant-123"
    assert retrieved.session_metadata["user_id"] == "user-456"
    assert retrieved.session_metadata["region"] == "us-east-1"
    assert retrieved.session_metadata["retention_profile"] == "standard"
    assert retrieved.session_metadata["data_flags"]["pii"] is True
    assert retrieved.session_metadata["custom_fields"]["department"] == "engineering"


@pytest.mark.usefixtures("client")
async def test_session_metadata_json_serialization():
    """Test that session_metadata is properly serialized as JSON."""
    session_id = f"json_test_session_{uuid4()}"
    metadata = {
        "tenant_id": "tenant-json",
        "nested": {"key1": "value1", "key2": [1, 2, 3]},
        "array": ["item1", "item2"],
        "number": 42,
        "boolean": True,
    }

    message = Message(
        text="JSON serialization test",
        sender="User",
        sender_name="Test User",
        session_id=session_id,
        session_metadata=metadata,
    )
    await astore_message(message)

    # Retrieve and verify complex JSON structure
    retrieved_messages = await aget_messages(sender="User", session_id=session_id)
    assert len(retrieved_messages) == 1
    retrieved_metadata = retrieved_messages[0].session_metadata

    assert retrieved_metadata["tenant_id"] == "tenant-json"
    assert retrieved_metadata["nested"]["key1"] == "value1"
    assert retrieved_metadata["nested"]["key2"] == [1, 2, 3]
    assert retrieved_metadata["array"] == ["item1", "item2"]
    assert retrieved_metadata["number"] == 42
    assert retrieved_metadata["boolean"] is True


@pytest.mark.usefixtures("client")
async def test_empty_session_metadata():
    """Test storing message with empty dict as session_metadata."""
    session_id = f"empty_metadata_session_{uuid4()}"
    message = Message(
        text="Empty metadata test",
        sender="User",
        sender_name="Test User",
        session_id=session_id,
        session_metadata={},
    )
    await astore_message(message)

    retrieved_messages = await aget_messages(sender="User", session_id=session_id)
    assert len(retrieved_messages) == 1
    assert retrieved_messages[0].session_metadata == {}


@pytest.mark.usefixtures("client")
async def test_session_metadata_retrieval():
    """Test retrieving session_metadata from stored messages."""
    session_id = f"retrieval_metadata_session_{uuid4()}"

    # Create initial message
    initial_metadata = {"tenant_id": "tenant-initial", "user_id": "user-initial"}
    message = Message(
        text="Initial message",
        sender="User",
        sender_name="Test User",
        session_id=session_id,
        session_metadata=initial_metadata,
    )
    await astore_message(message)

    # Retrieve and verify
    messages = await aget_messages(sender="User", session_id=session_id)
    assert len(messages) == 1
    assert messages[0].session_metadata == initial_metadata
