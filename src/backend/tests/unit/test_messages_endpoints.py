from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from langflow.memory import aadd_messagetables

# Assuming you have these imports available
from langflow.services.auth.utils import get_auth_service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message import MessageCreate, MessageRead, MessageUpdate
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import session_scope


@pytest.fixture
async def created_message(active_user):
    async with session_scope() as session:
        # Create a flow for the user so messages can be filtered by user
        flow = Flow(name="test_flow_for_message", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()

        message = MessageCreate(text="Test message", sender="User", sender_name="User", session_id="session_id")
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetable.flow_id = flow.id
        messagetables = await aadd_messagetables([messagetable], session)
        return MessageRead.model_validate(messagetables[0], from_attributes=True)


@pytest.fixture
async def other_active_user(client):  # noqa: ARG001
    username = f"other-user-{uuid4().hex[:8]}"
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_auth_service().get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)

    yield user

    async with session_scope() as session:
        db_user = await session.get(User, user.id)
        if db_user:
            await session.delete(db_user)


@pytest.fixture
async def other_logged_in_headers(client: AsyncClient, other_active_user):
    login_data = {"username": other_active_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def cross_user_messages(active_user, other_active_user):
    async with session_scope() as session:
        active_flow = Flow(
            name=f"active-flow-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []}
        )
        other_flow = Flow(
            name=f"other-flow-{uuid4().hex[:8]}",
            user_id=other_active_user.id,
            data={"nodes": [], "edges": []},
        )
        session.add(active_flow)
        session.add(other_flow)
        await session.flush()

        owned_message = MessageTable.model_validate(
            MessageCreate(text="Owned message", sender="User", sender_name="User", session_id="owned-session"),
            from_attributes=True,
        )
        owned_message.flow_id = active_flow.id

        foreign_message = MessageTable.model_validate(
            MessageCreate(text="Foreign message", sender="User", sender_name="User", session_id="foreign-session"),
            from_attributes=True,
        )
        foreign_message.flow_id = other_flow.id

        created_messages = await aadd_messagetables([owned_message, foreign_message], session)
        return {
            "owned_message": created_messages[0],
            "foreign_message": created_messages[1],
            "foreign_session_id": "foreign-session",
        }


@pytest.fixture
async def created_messages(session, active_user):  # noqa: ARG001
    async with session_scope() as _session:
        # Create a flow for the user so messages can be filtered by user
        flow = Flow(name="test_flow_for_messages", user_id=active_user.id, data={"nodes": [], "edges": []})
        _session.add(flow)
        await _session.flush()

        messages = [
            MessageCreate(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 3", sender="AI", sender_name="AI", session_id="session_id2"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        for mt in messagetables:
            mt.flow_id = flow.id
        return await aadd_messagetables(messagetables, _session)


@pytest.fixture
async def created_messages_multiple_sessions(session, active_user):  # noqa: ARG001
    """Create messages across multiple distinct sessions for bulk-delete testing."""
    async with session_scope() as _session:
        flow = Flow(name="test_flow_for_bulk_delete", user_id=active_user.id, data={"nodes": [], "edges": []})
        _session.add(flow)
        await _session.flush()

        messages = [
            MessageCreate(text="Session A msg 1", sender="User", sender_name="User", session_id="bulk_session_a"),
            MessageCreate(text="Session A msg 2", sender="AI", sender_name="AI", session_id="bulk_session_a"),
            MessageCreate(text="Session B msg 1", sender="User", sender_name="User", session_id="bulk_session_b"),
            MessageCreate(text="Session B msg 2", sender="AI", sender_name="AI", session_id="bulk_session_b"),
            MessageCreate(text="Session C msg 1", sender="User", sender_name="User", session_id="bulk_session_c"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        for mt in messagetables:
            mt.flow_id = flow.id
        return await aadd_messagetables(messagetables, _session)


@pytest.fixture
async def messages_with_datetime_session_id(session, active_user):  # noqa: ARG001
    """Create messages with datetime-like session IDs that contain characters requiring URL encoding."""
    datetime_session_id = "2024-01-15 10:30:45 UTC"  # Contains spaces and colons
    async with session_scope() as _session:
        # Create a flow for the user so messages can be filtered by user
        flow = Flow(name="test_flow_for_datetime_messages", user_id=active_user.id, data={"nodes": [], "edges": []})
        _session.add(flow)
        await _session.flush()

        messages = [
            MessageCreate(text="Datetime message 1", sender="User", sender_name="User", session_id=datetime_session_id),
            MessageCreate(text="Datetime message 2", sender="AI", sender_name="AI", session_id=datetime_session_id),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        for mt in messagetables:
            mt.flow_id = flow.id
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
async def test_get_messages_does_not_return_other_users_messages(
    client: AsyncClient, logged_in_headers, other_logged_in_headers, cross_user_messages
):
    response = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    returned_ids = {message["id"] for message in response.json()}
    assert str(cross_user_messages["owned_message"].id) in returned_ids
    assert str(cross_user_messages["foreign_message"].id) not in returned_ids

    other_response = await client.get("api/v1/monitor/messages", headers=other_logged_in_headers)
    assert other_response.status_code == 200, other_response.text
    other_returned_ids = {message["id"] for message in other_response.json()}
    assert str(cross_user_messages["foreign_message"].id) in other_returned_ids
    assert str(cross_user_messages["owned_message"].id) not in other_returned_ids


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
async def test_delete_messages_cannot_delete_other_users_messages(
    client: AsyncClient, logged_in_headers, cross_user_messages, other_logged_in_headers
):
    foreign_message_id = str(cross_user_messages["foreign_message"].id)

    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages",
        json=[foreign_message_id],
        headers=logged_in_headers,
    )
    assert response.status_code == 204, response.text

    own_view = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert own_view.status_code == 200, own_view.text
    assert str(cross_user_messages["owned_message"].id) in {message["id"] for message in own_view.json()}

    other_view = await client.get("api/v1/monitor/messages", headers=other_logged_in_headers)
    assert other_view.status_code == 200, other_view.text
    assert foreign_message_id in {message["id"] for message in other_view.json()}


@pytest.mark.api_key_required
async def test_update_message_cannot_update_other_users_message(
    client: AsyncClient, logged_in_headers, cross_user_messages, other_logged_in_headers
):
    foreign_message_id = cross_user_messages["foreign_message"].id
    response = await client.put(
        f"api/v1/monitor/messages/{foreign_message_id}",
        json=MessageUpdate(text="Hijacked").model_dump(),
        headers=logged_in_headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Message not found"

    other_view = await client.get("api/v1/monitor/messages", headers=other_logged_in_headers)
    assert other_view.status_code == 200, other_view.text
    foreign_message = next(message for message in other_view.json() if message["id"] == str(foreign_message_id))
    assert foreign_message["text"] == "Foreign message"


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


@pytest.mark.api_key_required
async def test_delete_messages_session_cannot_delete_other_users_messages(
    client: AsyncClient, logged_in_headers, cross_user_messages, other_logged_in_headers
):
    response = await client.delete(
        f"api/v1/monitor/messages/session/{cross_user_messages['foreign_session_id']}",
        headers=logged_in_headers,
    )
    assert response.status_code == 204, response.text

    own_view = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert own_view.status_code == 200, own_view.text
    assert str(cross_user_messages["owned_message"].id) in {message["id"] for message in own_view.json()}

    other_view = await client.get(
        "api/v1/monitor/messages",
        headers=other_logged_in_headers,
        params={"session_id": cross_user_messages["foreign_session_id"]},
    )
    assert other_view.status_code == 200, other_view.text
    assert len(other_view.json()) == 1
    assert other_view.json()[0]["id"] == str(cross_user_messages["foreign_message"].id)


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


@pytest.mark.api_key_required
async def test_update_session_id_cannot_modify_other_users_messages(
    client: AsyncClient, logged_in_headers, cross_user_messages, other_logged_in_headers
):
    response = await client.patch(
        f"api/v1/monitor/messages/session/{cross_user_messages['foreign_session_id']}",
        params={"new_session_id": "hijacked-session"},
        headers=logged_in_headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "No messages found with the given session ID"

    other_view = await client.get("api/v1/monitor/messages", headers=other_logged_in_headers)
    assert other_view.status_code == 200, other_view.text
    foreign_message = next(
        message for message in other_view.json() if message["id"] == str(cross_user_messages["foreign_message"].id)
    )
    assert foreign_message["session_id"] == cross_user_messages["foreign_session_id"]


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
    _created_messages, datetime_session_id = messages_with_datetime_session_id

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
    _created_messages, datetime_session_id = messages_with_datetime_session_id

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
async def test_get_messages_with_various_encoded_characters(client: AsyncClient, logged_in_headers, active_user):
    """Test various URL-encoded characters in session IDs."""
    # Create a session ID with various special characters
    special_session_id = "test+session:2024@domain.com"

    async with session_scope() as session:
        # Create a flow for the user so messages can be filtered by user
        flow = Flow(name="test_flow_for_special_chars", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()

        message = MessageCreate(
            text="Special chars message", sender="User", sender_name="User", session_id=special_session_id
        )
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetable.flow_id = flow.id
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


# ── Bulk delete sessions ──────────────────────────────────────────────────────


@pytest.mark.api_key_required
async def test_delete_messages_sessions_bulk(
    client: AsyncClient,
    created_messages_multiple_sessions,  # noqa: ARG001
    logged_in_headers,
):
    """Bulk-delete messages for multiple sessions in a single request."""
    session_ids = ["bulk_session_a", "bulk_session_b"]
    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages/sessions",
        json=session_ids,
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deleted_count"] == 2
    assert "Messages deleted successfully" in data["message"]

    # Verify that messages for the deleted sessions are gone
    for sid in session_ids:
        response = await client.get("api/v1/monitor/messages", params={"session_id": sid}, headers=logged_in_headers)
        assert response.status_code == 200
        assert response.json() == [], f"Expected no messages for session {sid!r}"

    # Verify that messages for the untouched session are still present
    response = await client.get(
        "api/v1/monitor/messages", params={"session_id": "bulk_session_c"}, headers=logged_in_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.api_key_required
async def test_delete_messages_sessions_all(
    client: AsyncClient,
    created_messages_multiple_sessions,  # noqa: ARG001
    logged_in_headers,
):
    """Bulk-delete messages for ALL sessions at once."""
    session_ids = ["bulk_session_a", "bulk_session_b", "bulk_session_c"]
    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages/sessions",
        json=session_ids,
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deleted_count"] == 3

    # All messages should be gone
    response = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api_key_required
async def test_delete_messages_sessions_empty_list(client: AsyncClient, logged_in_headers):
    """Bulk-delete with an empty list should succeed without error."""
    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages/sessions",
        json=[],
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deleted_count"] == 0
    assert "No sessions to delete" in data["message"]


@pytest.mark.api_key_required
async def test_delete_messages_sessions_nonexistent(client: AsyncClient, logged_in_headers):
    """Bulk-delete with session IDs that don't exist should succeed (no-op) and return 0 deleted."""
    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages/sessions",
        json=["nonexistent_session_1", "nonexistent_session_2"],
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    # Should return 0 since no sessions actually had messages deleted
    assert data["deleted_count"] == 0


@pytest.mark.api_key_required
async def test_delete_messages_sessions_partial_match(
    client: AsyncClient,
    created_messages_multiple_sessions,  # noqa: ARG001
    logged_in_headers,
):
    """Bulk-delete where some session IDs exist and some don't — only existing ones are removed."""
    session_ids = ["bulk_session_a", "does_not_exist"]
    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages/sessions",
        json=session_ids,
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    # Should return 1 since only bulk_session_a actually had messages deleted
    assert data["deleted_count"] == 1


@pytest.mark.api_key_required
async def test_delete_messages_sessions_exceeds_limit(client: AsyncClient, logged_in_headers):
    """Bulk-delete with more than 500 session IDs should return 400 error and not delete anything."""
    # Create a list of 501 session IDs
    session_ids = [f"session_{i}" for i in range(501)]
    response = await client.request(
        "DELETE",
        "api/v1/monitor/messages/sessions",
        json=session_ids,
        headers=logged_in_headers,
    )
    assert response.status_code == 400, response.text
    data = response.json()
    assert "Cannot delete more than 500 sessions" in data["detail"]
    # After a 400 error, no deletions should have occurred
    # The test validates the error response only
