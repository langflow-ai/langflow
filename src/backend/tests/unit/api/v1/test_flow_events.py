from httpx import AsyncClient
from starlette import status


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    """Create a minimal flow and return its id."""
    response = await client.post(
        "api/v1/flows/",
        json={"name": "event-test-flow", "data": {}},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


async def test_create_and_get_flow_events(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)

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
    flow_id = await _create_flow(client, logged_in_headers)

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
    flow_id = await _create_flow(client, logged_in_headers)

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
    flow_id = await _create_flow(client, logged_in_headers)

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


async def test_nonexistent_flow_returns_404(client: AsyncClient, logged_in_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"api/v1/flows/{fake_id}/events",
        params={"since": 0.0},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

    response = await client.post(
        f"api/v1/flows/{fake_id}/events",
        json={"type": "component_added", "summary": "Should fail"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
