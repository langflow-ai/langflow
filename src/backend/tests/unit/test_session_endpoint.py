from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.memory import aadd_messagetables
from langflow.services.database.models.message import MessageCreate
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture
async def messages_with_flow_ids(session):  # noqa: ARG001
    """Create messages with different session_ids and flow_ids for testing sessions endpoint."""
    async with session_scope() as _session:
        flow_id_1 = uuid4()
        flow_id_2 = uuid4()
        
        # Create MessageTable objects directly since MessageCreate doesn't have flow_id field
        messagetables = [
            MessageTable(
                text="Message 1", 
                sender="User", 
                sender_name="User", 
                session_id="session_A", 
                flow_id=flow_id_1
            ),
            MessageTable(
                text="Message 2", 
                sender="AI", 
                sender_name="AI", 
                session_id="session_A", 
                flow_id=flow_id_1
            ),
            MessageTable(
                text="Message 3", 
                sender="User", 
                sender_name="User", 
                session_id="session_B", 
                flow_id=flow_id_1
            ),
            MessageTable(
                text="Message 4", 
                sender="User", 
                sender_name="User", 
                session_id="session_C", 
                flow_id=flow_id_2
            ),
            MessageTable(
                text="Message 5", 
                sender="AI", 
                sender_name="AI", 
                session_id="session_D", 
                flow_id=flow_id_2
            ),
            MessageTable(
                text="Message 6", 
                sender="User", 
                sender_name="User", 
                session_id="session_E", 
                flow_id=None  # No flow_id
            ),
        ]
        created_messages = await aadd_messagetables(messagetables, _session)
        
        return {
            "messages": created_messages,
            "flow_id_1": flow_id_1,
            "flow_id_2": flow_id_2,
            "expected_sessions_flow_1": {"session_A", "session_B"},
            "expected_sessions_flow_2": {"session_C", "session_D"},
            "expected_all_sessions": {"session_A", "session_B", "session_C", "session_D", "session_E"}
        }


# Tests for /sessions endpoint
@pytest.mark.api_key_required
async def test_get_sessions_all(client: AsyncClient, logged_in_headers, messages_with_flow_ids):
    """Test getting all sessions without any filter."""
    response = await client.get("api/v1/monitor/sessions", headers=logged_in_headers)
    
    assert response.status_code == 200, response.text
    sessions = response.json()
    assert isinstance(sessions, list)
    
    # Convert to set for easier comparison since order doesn't matter
    returned_sessions = set(sessions)
    expected_sessions = messages_with_flow_ids["expected_all_sessions"]
    
    assert returned_sessions == expected_sessions
    assert len(sessions) == len(expected_sessions)


@pytest.mark.api_key_required
async def test_get_sessions_with_flow_id_filter(client: AsyncClient, logged_in_headers, messages_with_flow_ids):
    """Test getting sessions filtered by flow_id."""
    flow_id_1 = messages_with_flow_ids["flow_id_1"]
    
    response = await client.get(
        "api/v1/monitor/sessions", 
        params={"flow_id": str(flow_id_1)}, 
        headers=logged_in_headers
    )
    
    assert response.status_code == 200, response.text
    sessions = response.json()
    assert isinstance(sessions, list)
    
    returned_sessions = set(sessions)
    expected_sessions = messages_with_flow_ids["expected_sessions_flow_1"]
    
    assert returned_sessions == expected_sessions
    assert len(sessions) == len(expected_sessions)


@pytest.mark.api_key_required
async def test_get_sessions_with_different_flow_id(client: AsyncClient, logged_in_headers, messages_with_flow_ids):
    """Test getting sessions filtered by a different flow_id."""
    flow_id_2 = messages_with_flow_ids["flow_id_2"]
    
    response = await client.get(
        "api/v1/monitor/sessions", 
        params={"flow_id": str(flow_id_2)}, 
        headers=logged_in_headers
    )
    
    assert response.status_code == 200, response.text
    sessions = response.json()
    assert isinstance(sessions, list)
    
    returned_sessions = set(sessions)
    expected_sessions = messages_with_flow_ids["expected_sessions_flow_2"]
    
    assert returned_sessions == expected_sessions
    assert len(sessions) == len(expected_sessions)


@pytest.mark.api_key_required
async def test_get_sessions_with_non_existent_flow_id(client: AsyncClient, logged_in_headers):
    """Test getting sessions with a non-existent flow_id returns empty list."""
    non_existent_flow_id = uuid4()
    
    response = await client.get(
        "api/v1/monitor/sessions", 
        params={"flow_id": str(non_existent_flow_id)}, 
        headers=logged_in_headers
    )
    
    assert response.status_code == 200, response.text
    sessions = response.json()
    assert isinstance(sessions, list)
    assert len(sessions) == 0


@pytest.mark.api_key_required
async def test_get_sessions_empty_database(client: AsyncClient, logged_in_headers):
    """Test getting sessions when no messages exist in database."""
    response = await client.get("api/v1/monitor/sessions", headers=logged_in_headers)
    
    assert response.status_code == 200, response.text
    sessions = response.json()
    assert isinstance(sessions, list)
    assert len(sessions) == 0


@pytest.mark.api_key_required
async def test_get_sessions_invalid_flow_id_format(client: AsyncClient, logged_in_headers):
    """Test getting sessions with invalid flow_id format returns 422."""
    response = await client.get(
        "api/v1/monitor/sessions", 
        params={"flow_id": "invalid-uuid"}, 
        headers=logged_in_headers
    )
    
    assert response.status_code == 422, response.text
    assert "detail" in response.json()



