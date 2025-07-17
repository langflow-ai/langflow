from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

import pytest
from httpx import AsyncClient
from langflow.memory import aadd_messagetables

# Assuming you have these imports available
from langflow.services.database.models.message import MessageCreate, MessageRead, MessageUpdate
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture
async def created_message():
    async with session_scope() as session:
        message = MessageCreate(text="Test message", sender="User", sender_name="User", session_id="session_id")
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetables = await aadd_messagetables([messagetable], session)
        return MessageRead.model_validate(messagetables[0], from_attributes=True)


@pytest.fixture
async def created_messages(session):  # noqa: ARG001
    async with session_scope() as _session:
        messages = [
            MessageCreate(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 3", sender="AI", sender_name="AI", session_id="session_id2"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        return await aadd_messagetables(messagetables, _session)


@pytest.fixture
async def messages_with_datetime_session_id(session):  # noqa: ARG001
    """Create messages with datetime-like session IDs that contain characters requiring URL encoding."""
    datetime_session_id = "2024-01-15 10:30:45 UTC"  # Contains spaces and colons
    async with session_scope() as _session:
        messages = [
            MessageCreate(text="Datetime message 1", sender="User", sender_name="User", session_id=datetime_session_id),
            MessageCreate(text="Datetime message 2", sender="AI", sender_name="AI", session_id=datetime_session_id),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        created_messages = await aadd_messagetables(messagetables, _session)
        return created_messages, datetime_session_id


@pytest.mark.api_key_required
async def test_delete_messages(client: AsyncClient, created_messages, logged_in_headers):
    response = await client.request(
        "DELETE", "api/v1/monitor/messages", json=[str(msg.id) for msg in created_messages], headers=logged_in_headers
    )
    assert response.status_code == 204, response.text
    assert response.reason_phrase == "No Content"


@pytest.mark.api_key_required
async def test_update_message(client: AsyncClient, logged_in_headers, created_message):
    message_id = created_message.id
    message_update = MessageUpdate(text="Updated content")
    response = await client.put(
        f"api/v1/monitor/messages/{message_id}", json=message_update.model_dump(), headers=logged_in_headers
    )
    assert response.status_code == 200, response.text
    updated_message = MessageRead(**response.json())
    assert updated_message.text == "Updated content"


@pytest.mark.api_key_required
async def test_update_message_not_found(client: AsyncClient, logged_in_headers):
    non_existent_id = UUID("00000000-0000-0000-0000-000000000000")
    message_update = MessageUpdate(text="Updated content")
    response = await client.put(
        f"api/v1/monitor/messages/{non_existent_id}", json=message_update.model_dump(), headers=logged_in_headers
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Message not found"


@pytest.mark.api_key_required
async def test_delete_messages_session(client: AsyncClient, created_messages, logged_in_headers):
    session_id = "session_id2"
    response = await client.delete(f"api/v1/monitor/messages/session/{session_id}", headers=logged_in_headers)
    assert response.status_code == 204
    assert response.reason_phrase == "No Content"

    assert len(created_messages) == 3
    response = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0


# Successfully update session ID for all messages with the old session ID
@pytest.mark.usefixtures("session")
async def test_successfully_update_session_id(client, logged_in_headers, created_messages):
    old_session_id = "session_id2"
    new_session_id = "new_session_id"

    response = await client.patch(
        f"api/v1/monitor/messages/session/{old_session_id}",
        params={"new_session_id": new_session_id},
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    updated_messages = response.json()
    assert len(updated_messages) == len(created_messages)
    for message in updated_messages:
        assert message["session_id"] == new_session_id

    response = await client.get(
        "api/v1/monitor/messages", headers=logged_in_headers, params={"session_id": new_session_id}
    )
    assert response.status_code == 200
    assert len(response.json()) == len(created_messages)
    messages = response.json()
    for message in messages:
        assert message["session_id"] == new_session_id
        response_timestamp = message["timestamp"]
        timestamp = datetime.strptime(response_timestamp, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")
        assert timestamp_str == response_timestamp

    # Check if the messages ordered by timestamp are in the correct order
    # User, User, AI
    assert messages[0]["sender"] == "User"
    assert messages[1]["sender"] == "User"
    assert messages[2]["sender"] == "AI"


# No messages found with the given session ID
@pytest.mark.usefixtures("session")
async def test_no_messages_found_with_given_session_id(client, logged_in_headers):
    old_session_id = "non_existent_session_id"
    new_session_id = "new_session_id"

    response = await client.patch(
        f"/messages/session/{old_session_id}", params={"new_session_id": new_session_id}, headers=logged_in_headers
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Not Found"


# Test for URL-encoded datetime session ID
@pytest.mark.api_key_required
async def test_get_messages_with_url_encoded_datetime_session_id(
    client: AsyncClient, messages_with_datetime_session_id, logged_in_headers
):
    """Test that URL-encoded datetime session IDs are properly decoded and matched."""
    created_messages, datetime_session_id = messages_with_datetime_session_id

    # URL encode the datetime session ID (spaces become %20, colons become %3A)
    encoded_session_id = quote(datetime_session_id)

    # Test with URL-encoded session ID
    response = await client.get(
        "api/v1/monitor/messages", params={"session_id": encoded_session_id}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    messages = response.json()
    assert len(messages) == 2

    # Verify all messages have the correct (decoded) session ID
    for message in messages:
        assert message["session_id"] == datetime_session_id

    # Verify message content
    assert messages[0]["text"] == "Datetime message 1"
    assert messages[1]["text"] == "Datetime message 2"


@pytest.mark.api_key_required
async def test_get_messages_with_non_encoded_datetime_session_id(
    client: AsyncClient, messages_with_datetime_session_id, logged_in_headers
):
    """Test that non-URL-encoded datetime session IDs also work correctly."""
    created_messages, datetime_session_id = messages_with_datetime_session_id

    # Test with non-encoded session ID (should still work due to unquote being safe for non-encoded strings)
    response = await client.get(
        "api/v1/monitor/messages", params={"session_id": datetime_session_id}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    messages = response.json()
    assert len(messages) == 2

    # Verify all messages have the correct session ID
    for message in messages:
        assert message["session_id"] == datetime_session_id


@pytest.mark.api_key_required
async def test_get_messages_with_various_encoded_characters(client: AsyncClient, logged_in_headers):
    """Test various URL-encoded characters in session IDs."""
    # Create a session ID with various special characters
    special_session_id = "test+session:2024@domain.com"

    async with session_scope() as session:
        message = MessageCreate(
            text="Special chars message", sender="User", sender_name="User", session_id=special_session_id
        )
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        await aadd_messagetables([messagetable], session)

    # URL encode the session ID
    encoded_session_id = quote(special_session_id)

    # Test with URL-encoded session ID
    response = await client.get(
        "api/v1/monitor/messages", params={"session_id": encoded_session_id}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    messages = response.json()
    assert len(messages) == 1
    assert messages[0]["session_id"] == special_session_id
    assert messages[0]["text"] == "Special chars message"


@pytest.mark.api_key_required
async def test_get_messages_empty_result_with_encoded_nonexistent_session(client: AsyncClient, logged_in_headers):
    """Test that URL-encoded non-existent session IDs return empty results."""
    nonexistent_session_id = "2024-12-31 23:59:59 UTC"
    encoded_session_id = quote(nonexistent_session_id)

    response = await client.get(
        "api/v1/monitor/messages", params={"session_id": encoded_session_id}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    messages = response.json()
    assert len(messages) == 0
