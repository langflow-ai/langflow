"""Regression tests for bounded, recency-ordered monitor session lists."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.api.v1.monitor import router
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.user.model import User
from lfx.services.deps import injectable_session_scope

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def sessions_user(async_session):
    user = User(username="session-list-owner", password="unused", is_active=True)  # noqa: S106
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def sessions_flow(async_session, sessions_user):
    flow = Flow(name="Session list test", user_id=sessions_user.id, data={"nodes": [], "edges": []})
    async_session.add(flow)
    await async_session.flush()
    return flow


@pytest.fixture
async def sessions_client(async_session, sessions_user):
    """Exercise the real routes and SQL without starting unrelated app services."""
    app = FastAPI()
    app.include_router(router)

    async def database_override():
        yield async_session

    async def user_override():
        return sessions_user

    app.dependency_overrides[injectable_session_scope] = database_override
    app.dependency_overrides[get_current_active_user] = user_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(params=["flow", "all", "shared"])
def sessions_endpoint(request, sessions_flow, sessions_user):
    if request.param == "shared":
        return (
            "/monitor/messages/shared/sessions",
            {"source_flow_id": str(sessions_flow.id)},
            compute_virtual_flow_id(sessions_user.id, sessions_flow.id, principal_type="user"),
        )
    params = {"flow_id": str(sessions_flow.id)} if request.param == "flow" else {}
    return "/monitor/messages/sessions", params, sessions_flow.id


def _message(flow_id, session_id: str, age: int) -> MessageTable:
    return MessageTable(
        flow_id=flow_id,
        session_id=session_id,
        text="Session list regression",
        sender="User",
        sender_name="User",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=age),
        category="message",
        files=[],
        properties={},
        content_blocks=[],
    )


async def test_session_lists_bound_large_histories(sessions_client, async_session, sessions_endpoint):
    path, params, flow_id = sessions_endpoint
    count = 1000
    # Multiple messages per session must not consume multiple slots in a page.
    async_session.add_all(
        _message(flow_id, f"session-{index:04d}", index + duplicate)
        for index in range(count)
        for duplicate in (0, 10000)
    )
    await async_session.flush()
    expected = [f"session-{index:04d}" for index in reversed(range(count))]

    for query, size in (({}, 100), ({"limit": 0}, 100), ({"limit": 10000}, 200)):
        response = await sessions_client.get(path, params=params | query)
        assert response.status_code == 200, response.text
        assert response.json() == expected[:size]


async def test_session_pages_use_latest_message_and_stable_ties(sessions_client, async_session, sessions_endpoint):
    path, params, flow_id = sessions_endpoint
    async_session.add_all(
        [
            _message(flow_id, "old", 1),
            _message(flow_id, "recent", 2),
            _message(flow_id, "tie-z", 3),
            _message(flow_id, "tie-a", 3),
            _message(flow_id, "middle", 2),
            _message(flow_id, "recent", 4),
            # Insert an older message last; the session's MAX timestamp wins.
            _message(flow_id, "recent", 0),
        ]
    )
    await async_session.flush()
    expected = ["recent", "tie-a", "tie-z", "middle", "old"]
    pages = []
    for offset in (0, 2, 4, 6):
        response = await sessions_client.get(path, params=params | {"limit": 2, "offset": offset})
        assert response.status_code == 200, response.text
        assert response.json() == expected[offset : offset + 2]
        pages.extend(response.json())
    assert pages == expected


async def test_large_history_remains_accessible_by_paging(sessions_client, async_session, sessions_endpoint):
    path, params, flow_id = sessions_endpoint
    count = 231
    async_session.add_all(_message(flow_id, f"session-{index:03d}", index) for index in range(count))
    await async_session.flush()
    pages = []
    for offset in (0, 100, 200, 300):
        response = await sessions_client.get(path, params=params | {"offset": offset})
        assert response.status_code == 200, response.text
        pages.extend(response.json())
    assert pages == [f"session-{index:03d}" for index in reversed(range(count))]


@pytest.mark.parametrize("query", [{"limit": -1}, {"offset": -1}])
async def test_session_lists_reject_negative_pagination(sessions_client, sessions_endpoint, query):
    path, params, _ = sessions_endpoint
    response = await sessions_client.get(path, params=params | query)
    assert response.status_code == 422, response.text


async def test_session_filters_apply_before_grouping_and_pagination(
    sessions_client, async_session, sessions_endpoint, sessions_user, sessions_flow
):
    path, params, flow_id = sessions_endpoint
    foreign_user = User(username="foreign-session-owner", password="unused", is_active=True)  # noqa: S106
    foreign_flow = Flow(name="Foreign sessions", user_id=foreign_user.id, data={"nodes": [], "edges": []})
    async_session.add_all([foreign_user, foreign_flow])
    await async_session.flush()
    async_session.add_all(
        [
            _message(flow_id, "visible-a", 3),
            _message(flow_id, "visible-b", 2),
            _message(flow_id, "visible-c", 1),
            _message(foreign_flow.id, "foreign", 100),
            # A foreign row with the same session ID must not change recency.
            _message(foreign_flow.id, "visible-c", 100),
            _message(uuid4(), "orphan", 100),
        ]
    )
    if "shared" in path:
        foreign_virtual_id = compute_virtual_flow_id(foreign_user.id, sessions_flow.id, principal_type="user")
        other_source_virtual_id = compute_virtual_flow_id(sessions_user.id, uuid4(), principal_type="user")
        async_session.add_all(
            [
                _message(foreign_virtual_id, "foreign-user", 100),
                _message(other_source_virtual_id, "other-source", 100),
                _message(sessions_flow.id, "original-flow", 100),
            ]
        )
    else:
        async_session.add(_message(flow_id, "agentic_hidden", 100))
        if "flow_id" in params:
            other_owned_flow = Flow(name="Other owned flow", user_id=sessions_user.id, data={"nodes": [], "edges": []})
            async_session.add(other_owned_flow)
            await async_session.flush()
            async_session.add(_message(other_owned_flow.id, "other-owned-flow", 100))
    await async_session.flush()

    for offset, expected in ((0, ["visible-a", "visible-b"]), (2, ["visible-c"]), (3, [])):
        response = await sessions_client.get(path, params=params | {"limit": 2, "offset": offset})
        assert response.status_code == 200, response.text
        assert response.json() == expected


async def test_all_flows_group_sessions_across_owned_flows(
    sessions_client, async_session, sessions_user, sessions_flow
):
    second_flow = Flow(name="Second owned flow", user_id=sessions_user.id, data={"nodes": [], "edges": []})
    async_session.add(second_flow)
    await async_session.flush()
    async_session.add_all(
        [
            _message(sessions_flow.id, "reused-session", 1),
            _message(sessions_flow.id, "middle-session", 2),
            _message(second_flow.id, "reused-session", 3),
        ]
    )
    await async_session.flush()
    response = await sessions_client.get("/monitor/messages/sessions", params={"limit": 1})
    assert response.status_code == 200, response.text
    assert response.json() == ["reused-session"]
    response = await sessions_client.get("/monitor/messages/sessions", params={"limit": 1, "offset": 1})
    assert response.status_code == 200, response.text
    assert response.json() == ["middle-session"]


async def test_session_lists_do_not_expose_foreign_flow(sessions_client, async_session):
    foreign_user = User(username="foreign-flow-owner", password="unused", is_active=True)  # noqa: S106
    foreign_flow = Flow(name="Foreign flow", user_id=foreign_user.id, data={"nodes": [], "edges": []})
    async_session.add_all([foreign_user, foreign_flow])
    await async_session.flush()
    async_session.add(_message(foreign_flow.id, "private-session", 1))
    await async_session.flush()
    for flow_id in (foreign_flow.id, uuid4()):
        response = await sessions_client.get("/monitor/messages/sessions", params={"flow_id": str(flow_id), "limit": 1})
        assert response.status_code == 200, response.text
        assert response.json() == []
