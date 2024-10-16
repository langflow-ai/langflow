from uuid import UUID

import pytest
from httpx import AsyncClient
from langflow.memory import add_messagetables

# Assuming you have these imports available
from langflow.services.database.models.message import MessageCreate, MessageRead, MessageUpdate
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture
async def created_message():
    with session_scope() as session:
        message = MessageCreate(text="Test message", sender="User", sender_name="User", session_id="session_id")
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetables = add_messagetables([messagetable], session)
        return MessageRead.model_validate(messagetables[0], from_attributes=True)


@pytest.fixture
def created_messages(session):
    with session_scope() as session:
        messages = [
            MessageCreate(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 3", sender="User", sender_name="User", session_id="session_id2"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        return add_messagetables(messagetables, session)


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
    for message in response.json():
        assert message["session_id"] == new_session_id


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
