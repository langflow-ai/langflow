from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from langflow.api.v1 import authz_route_dependencies
from langflow.services.authorization import FlowAction
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_flow_events_service, session_scope
from starlette import status

from tests.unit.services.authorization._policy_double import create_user_share, install_policy_authz


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


async def test_invalid_event_type_returns_422(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)

    response = await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "invalid_type", "summary": "bad event"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_missing_event_type_returns_422(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)

    response = await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"summary": "no type field"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_summary_max_length_returns_422(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)

    response = await client.post(
        f"api/v1/flows/{flow_id}/events",
        json={"type": "component_added", "summary": "x" * 501},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("ownerless", [False, True])
async def test_events_require_an_accessible_flow(client: AsyncClient, logged_in_headers, user_two, ownerless):
    async with session_scope() as session:
        flow = Flow(name="inaccessible-events", data={}, user_id=None if ownerless else user_two.id)
        session.add(flow)
        await session.flush()
        flow_id = flow.id

    try:
        response = await client.get(f"api/v1/flows/{flow_id}/events", headers=logged_in_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response = await client.post(
            f"api/v1/flows/{flow_id}/events",
            json={"type": "flow_updated", "summary": "Test event"},
            headers=logged_in_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        events, _ = get_flow_events_service().get_since(str(flow_id), 0)
        assert events == []
    finally:
        async with session_scope() as session:
            await session.delete(await session.get(Flow, flow_id))


@pytest.mark.parametrize(("method", "action"), [("GET", FlowAction.READ), ("POST", FlowAction.WRITE)])
async def test_events_check_the_matching_permission(
    client: AsyncClient, logged_in_headers, monkeypatch, method, action
):
    flow_id = await _create_flow(client, logged_in_headers)
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(flow_id))
        owner_id, workspace_id, folder_id = flow.user_id, flow.workspace_id, flow.folder_id
    guard = AsyncMock()
    monkeypatch.setattr(authz_route_dependencies, "ensure_flow_permission", guard)

    response = await client.request(
        method,
        f"api/v1/flows/{flow_id}/events",
        headers=logged_in_headers,
        **({"json": {"type": "flow_updated"}} if method == "POST" else {}),
    )

    assert response.status_code == (201 if method == "POST" else 200)
    guard.assert_awaited_once()
    assert guard.await_args.args[1] == action
    assert guard.await_args.kwargs == {
        "flow_id": UUID(flow_id),
        "flow_user_id": owner_id,
        "workspace_id": workspace_id,
        "folder_id": folder_id,
    }


@pytest.mark.parametrize(("method", "readable"), [("GET", False), ("POST", False), ("POST", True)])
async def test_events_honor_permission_denials(client: AsyncClient, logged_in_headers, monkeypatch, method, readable):
    flow_id = await _create_flow(client, logged_in_headers)

    async def enforce_permission(_user, action, **_kwargs):
        if readable and action == FlowAction.READ:
            return
        raise HTTPException(status_code=403, detail="Permission denied")

    monkeypatch.setattr(authz_route_dependencies, "ensure_flow_permission", enforce_permission)
    response = await client.request(
        method,
        f"api/v1/flows/{flow_id}/events",
        headers=logged_in_headers,
        **({"json": {"type": "flow_updated"}} if method == "POST" else {}),
    )

    assert response.status_code == (403 if readable else 404)
    events, _ = get_flow_events_service().get_since(flow_id, 0)
    assert events == []


@pytest.mark.parametrize("permission", ["write", "read", None])
async def test_events_enforce_stored_shares_for_non_owners(
    client: AsyncClient, logged_in_headers, active_user, user_two, permission
):
    """Stored shares govern event access through the real fetch and permission guards."""
    from langflow.services.deps import get_settings_service

    async with session_scope() as session:
        flow = Flow(name="shared-events", data={}, user_id=user_two.id)
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        if permission:
            await create_user_share(
                session,
                resource_type="flow",
                resource_id=flow_id,
                target_user_id=active_user.id,
                permission_level=permission,
                created_by=user_two.id,
            )

    try:
        with install_policy_authz(get_settings_service()):
            read = await client.get(f"api/v1/flows/{flow_id}/events", headers=logged_in_headers)
            assert read.status_code == (200 if permission else 404)
            write = await client.post(
                f"api/v1/flows/{flow_id}/events",
                json={"type": "flow_updated", "summary": "Shared event"},
                headers=logged_in_headers,
            )
            assert write.status_code == ({"write": 201, "read": 403, None: 404}[permission])
            if permission == "write":
                read = await client.get(f"api/v1/flows/{flow_id}/events", headers=logged_in_headers)
                assert read.status_code == 200
                assert read.json()["events"][0]["summary"] == "Shared event"
        events, _ = get_flow_events_service().get_since(str(flow_id), 0)
        assert [event.summary for event in events] == (["Shared event"] if permission == "write" else [])
    finally:
        async with session_scope() as session:
            await session.delete(await session.get(Flow, flow_id))
