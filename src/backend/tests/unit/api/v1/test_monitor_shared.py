"""Tests for shared playground monitor endpoints.

These endpoints allow authenticated users to retrieve and manage messages
from public/shared flows. Messages are scoped by a virtual flow_id
derived from the user's ID and the original flow ID.
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.services.database.models.message.model import MessageTable
from lfx.services.deps import session_scope

# --- Unit tests for compute_virtual_flow_id ---


def test_compute_virtual_flow_id_is_deterministic():
    """Same inputs always produce the same virtual flow_id."""
    user_id = uuid.uuid4()
    flow_id = uuid.uuid4()

    result_1 = compute_virtual_flow_id(user_id, flow_id)
    result_2 = compute_virtual_flow_id(user_id, flow_id)

    assert result_1 == result_2


def test_compute_virtual_flow_id_differs_per_user():
    """Different users produce different virtual flow_ids for the same flow."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    flow_id = uuid.uuid4()

    result_a = compute_virtual_flow_id(user_a, flow_id)
    result_b = compute_virtual_flow_id(user_b, flow_id)

    assert result_a != result_b


def test_compute_virtual_flow_id_differs_per_flow():
    """Same user produces different virtual flow_ids for different flows."""
    user_id = uuid.uuid4()
    flow_a = uuid.uuid4()
    flow_b = uuid.uuid4()

    result_a = compute_virtual_flow_id(user_id, flow_a)
    result_b = compute_virtual_flow_id(user_id, flow_b)

    assert result_a != result_b


def test_compute_virtual_flow_id_accepts_string_identifier():
    """String identifiers (client_id) work the same way."""
    client_id = "test-client-123"
    flow_id = uuid.uuid4()

    result = compute_virtual_flow_id(client_id, flow_id)

    assert isinstance(result, uuid.UUID)


def test_compute_virtual_flow_id_returns_uuid():
    """Result is always a valid UUID."""
    result = compute_virtual_flow_id(uuid.uuid4(), uuid.uuid4())
    assert isinstance(result, uuid.UUID)


# --- Auth requirement tests for shared endpoints ---


FAKE_FLOW_ID = "00000000-0000-0000-0000-000000000001"


async def test_get_shared_sessions_requires_auth(client: AsyncClient):
    response = await client.get(f"api/v1/monitor/messages/shared/sessions?source_flow_id={FAKE_FLOW_ID}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_shared_messages_requires_auth(client: AsyncClient):
    response = await client.get(f"api/v1/monitor/messages/shared?source_flow_id={FAKE_FLOW_ID}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_delete_shared_session_requires_auth(client: AsyncClient):
    response = await client.delete(f"api/v1/monitor/messages/shared/session/test-session?source_flow_id={FAKE_FLOW_ID}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_rename_shared_session_requires_auth(client: AsyncClient):
    response = await client.patch(
        f"api/v1/monitor/messages/shared/session/old-session?new_session_id=new-session&source_flow_id={FAKE_FLOW_ID}"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_update_shared_message_requires_auth(client: AsyncClient):
    fake_msg_id = "00000000-0000-0000-0000-000000000002"
    response = await client.put(
        f"api/v1/monitor/messages/shared/{fake_msg_id}?source_flow_id={FAKE_FLOW_ID}",
        json={"text": "updated"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Functional tests with authenticated users ---


@pytest.fixture
async def shared_messages_setup(active_user):
    """Create test messages with a virtual flow_id scoped to active_user."""
    source_flow_id = uuid.uuid4()
    virtual_flow_id = compute_virtual_flow_id(active_user.id, source_flow_id)

    async with session_scope() as session:
        for i in range(3):
            msg = MessageTable(
                text=f"Test message {i}",
                sender="User" if i % 2 == 0 else "Machine",
                sender_name="User" if i % 2 == 0 else "AI",
                session_id="test-session-1",
                flow_id=virtual_flow_id,
                category="message",
                files=[],
                properties={},
                content_blocks=[],
            )
            session.add(msg)

        # Add a message in a different session
        msg_other_session = MessageTable(
            text="Message in session 2",
            sender="User",
            sender_name="User",
            session_id="test-session-2",
            flow_id=virtual_flow_id,
            category="message",
            files=[],
            properties={},
            content_blocks=[],
        )
        session.add(msg_other_session)

    return {"source_flow_id": source_flow_id, "virtual_flow_id": virtual_flow_id}


@pytest.mark.usefixtures("active_user")
async def test_get_shared_sessions_returns_user_sessions(client: AsyncClient, logged_in_headers, shared_messages_setup):
    source_flow_id = shared_messages_setup["source_flow_id"]
    response = await client.get(
        f"api/v1/monitor/messages/shared/sessions?source_flow_id={source_flow_id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    sessions = response.json()
    assert isinstance(sessions, list)
    assert "test-session-1" in sessions
    assert "test-session-2" in sessions


@pytest.mark.usefixtures("active_user")
async def test_get_shared_messages_returns_messages(client: AsyncClient, logged_in_headers, shared_messages_setup):
    source_flow_id = shared_messages_setup["source_flow_id"]
    response = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}&session_id=test-session-1",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    messages = response.json()
    assert isinstance(messages, list)
    assert len(messages) == 3


@pytest.mark.usefixtures("active_user", "shared_messages_setup")
async def test_get_shared_messages_empty_for_wrong_flow(client: AsyncClient, logged_in_headers):
    """Requesting messages for a flow the user hasn't interacted with returns empty."""
    random_flow_id = uuid.uuid4()
    response = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={random_flow_id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.mark.usefixtures("active_user")
async def test_delete_shared_session_removes_messages(client: AsyncClient, logged_in_headers, shared_messages_setup):
    source_flow_id = shared_messages_setup["source_flow_id"]

    # Delete session-1
    response = await client.delete(
        f"api/v1/monitor/messages/shared/session/test-session-1?source_flow_id={source_flow_id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify session-1 messages are gone
    response = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}&session_id=test-session-1",
        headers=logged_in_headers,
    )
    assert response.json() == []

    # Verify session-2 messages still exist
    response = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}&session_id=test-session-2",
        headers=logged_in_headers,
    )
    assert len(response.json()) == 1


@pytest.mark.usefixtures("active_user")
async def test_rename_shared_session(client: AsyncClient, logged_in_headers, shared_messages_setup):
    source_flow_id = shared_messages_setup["source_flow_id"]

    response = await client.patch(
        f"api/v1/monitor/messages/shared/session/test-session-1"
        f"?new_session_id=renamed-session&source_flow_id={source_flow_id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    messages = response.json()
    assert len(messages) == 3
    assert all(m["session_id"] == "renamed-session" for m in messages)


# --- User isolation tests ---


@pytest.mark.usefixtures("active_user")
async def test_shared_messages_isolated_between_users(
    client: AsyncClient, logged_in_headers, shared_messages_setup, user_two
):
    """User B cannot see User A's shared playground messages via API."""
    source_flow_id = shared_messages_setup["source_flow_id"]

    # User A can see their messages
    response_a = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}",
        headers=logged_in_headers,
    )
    assert response_a.status_code == status.HTTP_200_OK
    assert len(response_a.json()) == 4  # 3 in session-1 + 1 in session-2

    # Log in as User B
    login_data = {"username": user_two.username, "password": "hashed_password"}
    login_response = await client.post("api/v1/login", data=login_data)
    assert login_response.status_code == 200
    user_b_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    # User B sees EMPTY messages for the same source_flow_id
    response_b = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}",
        headers=user_b_headers,
    )
    assert response_b.status_code == status.HTTP_200_OK
    assert response_b.json() == []

    # User B also sees no sessions
    response_b_sessions = await client.get(
        f"api/v1/monitor/messages/shared/sessions?source_flow_id={source_flow_id}",
        headers=user_b_headers,
    )
    assert response_b_sessions.status_code == status.HTTP_200_OK
    assert response_b_sessions.json() == []


@pytest.mark.usefixtures("active_user")
async def test_update_shared_message_updates_properties(client: AsyncClient, logged_in_headers, shared_messages_setup):
    """PUT /messages/shared/{id} should update message properties."""
    source_flow_id = shared_messages_setup["source_flow_id"]

    # Get a message to update
    response = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}&session_id=test-session-1",
        headers=logged_in_headers,
    )
    messages = response.json()
    assert len(messages) > 0
    message_id = messages[0]["id"]

    # Update the message properties with build_duration
    response = await client.put(
        f"api/v1/monitor/messages/shared/{message_id}?source_flow_id={source_flow_id}",
        headers=logged_in_headers,
        json={"properties": {"build_duration": 1500}},
    )
    assert response.status_code == status.HTTP_200_OK
    updated = response.json()
    assert updated["properties"]["build_duration"] == 1500


@pytest.mark.usefixtures("active_user")
async def test_update_shared_message_returns_404_for_wrong_flow(
    client: AsyncClient, logged_in_headers, shared_messages_setup
):
    """PUT with wrong source_flow_id should return 404."""
    source_flow_id = shared_messages_setup["source_flow_id"]

    # Get a real message ID
    response = await client.get(
        f"api/v1/monitor/messages/shared?source_flow_id={source_flow_id}",
        headers=logged_in_headers,
    )
    message_id = response.json()[0]["id"]

    # Try to update with a different source_flow_id
    wrong_flow_id = uuid.uuid4()
    response = await client.put(
        f"api/v1/monitor/messages/shared/{message_id}?source_flow_id={wrong_flow_id}",
        headers=logged_in_headers,
        json={"properties": {"build_duration": 9999}},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("active_user")
async def test_update_shared_message_returns_404_for_nonexistent_id(
    client: AsyncClient, logged_in_headers, shared_messages_setup
):
    """PUT with nonexistent message ID should return 404."""
    source_flow_id = shared_messages_setup["source_flow_id"]
    fake_msg_id = uuid.uuid4()

    response = await client.put(
        f"api/v1/monitor/messages/shared/{fake_msg_id}?source_flow_id={source_flow_id}",
        headers=logged_in_headers,
        json={"text": "should not work"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_compute_virtual_flow_id_differs_between_users():
    """Unit-level confirmation that different users get different virtual flow_ids."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    flow_id = uuid.uuid4()

    assert compute_virtual_flow_id(user_a, flow_id) != compute_virtual_flow_id(user_b, flow_id)
