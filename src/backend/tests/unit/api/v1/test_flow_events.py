from httpx import AsyncClient
from starlette import status


async def test_create_and_get_flow_events(client: AsyncClient, logged_in_headers):
    flow_id = "test-flow-123"

    response = await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "component_added", "summary": "Added OpenAI"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    event = response.json()
    assert event["type"] == "component_added"
    assert event["summary"] == "Added OpenAI"
    assert "timestamp" in event

    response = await client.get(
        f"api/v1/flows/{flow_id}/events",
        params={"since": 0.0},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "component_added"
    assert data["settled"] is False


async def test_get_events_cursor_based(client: AsyncClient, logged_in_headers):
    flow_id = "test-flow-cursor"

    r1 = await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "component_added", "summary": "First"},
        headers=logged_in_headers,
    )
    first_ts = r1.json()["timestamp"]

    await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "connection_added", "summary": "Second"},
        headers=logged_in_headers,
    )

    response = await client.get(
        f"api/v1/flows/{flow_id}/events",
        params={"since": first_ts},
        headers=logged_in_headers,
    )
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["summary"] == "Second"


async def test_settled_on_flow_settled_event(client: AsyncClient, logged_in_headers):
    flow_id = "test-flow-settled"

    await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "component_added", "summary": "Added"},
        headers=logged_in_headers,
    )
    await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "flow_settled", "summary": "Done"},
        headers=logged_in_headers,
    )

    response = await client.get(
        f"api/v1/flows/{flow_id}/events",
        params={"since": 0.0},
        headers=logged_in_headers,
    )
    data = response.json()
    assert data["settled"] is True


async def test_full_event_lifecycle(client: AsyncClient, logged_in_headers):
    """Simulate: MCP emits events -> frontend polls -> detects settle."""
    flow_id = "integration-test-flow"

    await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "component_added", "summary": "Added OpenAI"},
        headers=logged_in_headers,
    )
    await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "connection_added", "summary": "Connected to Chat Output"},
        headers=logged_in_headers,
    )

    response = await client.get(
        f"api/v1/flows/{flow_id}/events",
        params={"since": 0.0},
        headers=logged_in_headers,
    )
    data = response.json()
    assert len(data["events"]) == 2
    assert data["settled"] is False

    await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "flow_settled", "summary": "Built a RAG pipeline"},
        headers=logged_in_headers,
    )

    response = await client.get(
        f"api/v1/flows/{flow_id}/events",
        params={"since": 0.0},
        headers=logged_in_headers,
    )
    data = response.json()
    assert len(data["events"]) == 3
    assert data["settled"] is True
    assert any(e["type"] == "flow_settled" for e in data["events"])
