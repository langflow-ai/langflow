"""Tests for background agent API endpoints."""

from uuid import uuid4

from fastapi import status
from httpx import AsyncClient


async def test_create_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test creating a new background agent."""
    agent_data = {
        "name": "Test Agent",
        "description": "A test background agent",
        "flow_id": str(test_flow.id),
        "trigger_type": "INTERVAL",
        "trigger_config": {"minutes": 5},
        "input_config": {"input_value": "test", "input_type": "chat"},
        "enabled": True,
    }

    response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict)
    assert result["name"] == agent_data["name"]
    assert result["description"] == agent_data["description"]
    assert result["flow_id"] == agent_data["flow_id"]
    assert result["trigger_type"] == agent_data["trigger_type"]
    assert result["status"] == "STOPPED"
    assert result["enabled"] == agent_data["enabled"]
    assert "id" in result
    assert "user_id" in result


async def test_list_background_agents(client: AsyncClient, logged_in_headers, test_flow):
    """Test listing background agents."""
    # Create a test agent first
    agent_data = {
        "name": "Test Agent List",
        "flow_id": str(test_flow.id),
        "trigger_type": "CRON",
        "trigger_config": {"minute": "0", "hour": "*/2"},
        "input_config": {},
    }

    await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)

    # List agents
    response = await client.get("api/v1/background_agents/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list)
    assert len(result) > 0


async def test_list_background_agents_by_flow(client: AsyncClient, logged_in_headers, test_flow):
    """Test listing background agents filtered by flow_id."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Filter",
        "flow_id": str(test_flow.id),
        "trigger_type": "WEBHOOK",
        "trigger_config": {},
        "input_config": {},
    }

    await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)

    # List agents for this flow
    response = await client.get(
        "api/v1/background_agents/", params={"flow_id": str(test_flow.id)}, headers=logged_in_headers
    )
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list)
    # All returned agents should have the same flow_id
    for agent in result:
        assert agent["flow_id"] == str(test_flow.id)


async def test_get_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test getting a specific background agent."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Get",
        "flow_id": str(test_flow.id),
        "trigger_type": "INTERVAL",
        "trigger_config": {"hours": 1},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Get the agent
    response = await client.get(f"api/v1/background_agents/{agent_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["id"] == agent_id
    assert result["name"] == agent_data["name"]


async def test_update_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test updating a background agent."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Update",
        "flow_id": str(test_flow.id),
        "trigger_type": "INTERVAL",
        "trigger_config": {"minutes": 10},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Update the agent
    update_data = {
        "name": "Updated Agent Name",
        "trigger_config": {"minutes": 15},
    }

    response = await client.patch(f"api/v1/background_agents/{agent_id}", json=update_data, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["name"] == update_data["name"]
    assert result["trigger_config"]["minutes"] == 15


async def test_delete_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test deleting a background agent."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Delete",
        "flow_id": str(test_flow.id),
        "trigger_type": "DATE",
        "trigger_config": {"run_date": "2025-12-31T23:59:59Z"},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Delete the agent
    response = await client.delete(f"api/v1/background_agents/{agent_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's deleted
    get_response = await client.get(f"api/v1/background_agents/{agent_id}", headers=logged_in_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_start_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test starting a background agent."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Start",
        "flow_id": str(test_flow.id),
        "trigger_type": "INTERVAL",
        "trigger_config": {"minutes": 30},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Start the agent
    response = await client.post(f"api/v1/background_agents/{agent_id}/start", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["status"] == "started"
    assert result["agent_id"] == agent_id


async def test_stop_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test stopping a background agent."""
    # Create and start a test agent
    agent_data = {
        "name": "Test Agent Stop",
        "flow_id": str(test_flow.id),
        "trigger_type": "INTERVAL",
        "trigger_config": {"minutes": 45},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    await client.post(f"api/v1/background_agents/{agent_id}/start", headers=logged_in_headers)

    # Stop the agent
    response = await client.post(f"api/v1/background_agents/{agent_id}/stop", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["status"] == "stopped"
    assert result["agent_id"] == agent_id


async def test_pause_resume_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test pausing and resuming a background agent."""
    # Create and start a test agent
    agent_data = {
        "name": "Test Agent Pause",
        "flow_id": str(test_flow.id),
        "trigger_type": "CRON",
        "trigger_config": {"minute": "*/15"},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    await client.post(f"api/v1/background_agents/{agent_id}/start", headers=logged_in_headers)

    # Pause the agent
    pause_response = await client.post(f"api/v1/background_agents/{agent_id}/pause", headers=logged_in_headers)
    pause_result = pause_response.json()

    assert pause_response.status_code == status.HTTP_200_OK
    assert pause_result["status"] == "paused"

    # Resume the agent
    resume_response = await client.post(f"api/v1/background_agents/{agent_id}/resume", headers=logged_in_headers)
    resume_result = resume_response.json()

    assert resume_response.status_code == status.HTTP_200_OK
    assert resume_result["status"] == "active"


async def test_trigger_background_agent(client: AsyncClient, logged_in_headers, test_flow):
    """Test manually triggering a background agent."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Trigger",
        "flow_id": str(test_flow.id),
        "trigger_type": "WEBHOOK",
        "trigger_config": {},
        "input_config": {"input_value": "manual trigger test"},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Trigger the agent
    response = await client.post(f"api/v1/background_agents/{agent_id}/trigger", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["status"] == "triggered"
    assert result["agent_id"] == agent_id
    assert "execution_id" in result


async def test_get_agent_status(client: AsyncClient, logged_in_headers, test_flow):
    """Test getting agent status."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Status",
        "flow_id": str(test_flow.id),
        "trigger_type": "INTERVAL",
        "trigger_config": {"hours": 2},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Get status
    response = await client.get(f"api/v1/background_agents/{agent_id}/status", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["agent_id"] == agent_id
    assert result["name"] == agent_data["name"]
    assert "status" in result
    assert "enabled" in result
    assert "trigger_type" in result


async def test_get_agent_executions(client: AsyncClient, logged_in_headers, test_flow):
    """Test getting agent execution history."""
    # Create a test agent
    agent_data = {
        "name": "Test Agent Executions",
        "flow_id": str(test_flow.id),
        "trigger_type": "EVENT",
        "trigger_config": {},
        "input_config": {},
    }

    create_response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)
    agent_id = create_response.json()["id"]

    # Get executions (should be empty initially)
    response = await client.get(f"api/v1/background_agents/{agent_id}/executions", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "executions" in result
    assert "count" in result
    assert isinstance(result["executions"], list)


async def test_create_agent_with_invalid_flow(client: AsyncClient, logged_in_headers):
    """Test creating an agent with non-existent flow."""
    agent_data = {
        "name": "Invalid Agent",
        "flow_id": str(uuid4()),  # Non-existent flow
        "trigger_type": "INTERVAL",
        "trigger_config": {"minutes": 10},
        "input_config": {},
    }

    response = await client.post("api/v1/background_agents/", json=agent_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_nonexistent_agent(client: AsyncClient, logged_in_headers):
    """Test getting a non-existent agent."""
    fake_id = str(uuid4())

    response = await client.get(f"api/v1/background_agents/{fake_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_unauthorized_access(client: AsyncClient):
    """Test accessing background agents without authentication."""
    response = await client.get("api/v1/background_agents/")

    # Should require authentication
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
