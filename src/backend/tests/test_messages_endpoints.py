from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from langflow.memory import add_messagetables

# Assuming you have these imports available
from langflow.services.database.models.message import MessageCreate, MessageRead, MessageUpdate
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture()
def created_message():
    with session_scope() as session:
        message = MessageCreate(text="Test message", sender="User", sender_name="User", session_id="session_id")
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetables = add_messagetables([messagetable], session)
        message_read = MessageRead.model_validate(messagetables[0], from_attributes=True)
        return message_read


@pytest.fixture()
def created_messages(session):
    with session_scope() as session:
        messages = [
            MessageCreate(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 3", sender="User", sender_name="User", session_id="session_id2"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        message_list = add_messagetables(messagetables, session)

        return message_list


def test_delete_messages(client: TestClient, created_messages, logged_in_headers):
    response = client.request(
        "DELETE", "api/v1/monitor/messages", json=[str(msg.id) for msg in created_messages], headers=logged_in_headers
    )
    assert response.status_code == 204, response.text
    assert response.reason_phrase == "No Content"


def test_update_message(client: TestClient, logged_in_headers, created_message):
    message_id = created_message.id
    message_update = MessageUpdate(text="Updated content")
    response = client.put(
        f"api/v1/monitor/messages/{message_id}", json=message_update.model_dump(), headers=logged_in_headers
    )
    assert response.status_code == 200, response.text
    updated_message = MessageRead(**response.json())
    assert updated_message.text == "Updated content"


def test_update_message_not_found(client: TestClient, logged_in_headers):
    non_existent_id = UUID("00000000-0000-0000-0000-000000000000")
    message_update = MessageUpdate(text="Updated content")
    response = client.put(
        f"api/v1/monitor/messages/{non_existent_id}", json=message_update.model_dump(), headers=logged_in_headers
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Message not found"


def test_delete_messages_session(client: TestClient, created_messages, logged_in_headers):
    session_id = "session_id2"
    response = client.delete(f"api/v1/monitor/messages/session/{session_id}", headers=logged_in_headers)
    assert response.status_code == 204
    assert response.reason_phrase == "No Content"

    assert len(created_messages) == 3
    response = client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0
