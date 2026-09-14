from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.memory import aadd_messagetables
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture(params=["messages", "messages/shared"])
async def message_history(request, active_user):
    """Use tied timestamps and distinct sort values for both authenticated routes."""
    async with session_scope() as session:
        flow = Flow(name="pagination-test", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        shared = request.param == "messages/shared"
        flow_id = compute_virtual_flow_id(active_user.id, flow.id, principal_type="user") if shared else flow.id
        params = {"source_flow_id" if shared else "flow_id": str(flow.id)}
        id_prefix = (uuid4().int >> 32) << 32
        messages = [
            MessageTable(
                id=UUID(int=id_prefix + index + 1),
                flow_id=flow_id,
                files=[],
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index // 5),
                sender="User" if index % 2 else "Machine",
                sender_name=f"Sender {249 - index:03d}",
                text=f"Message {index:03d}",
                session_id=f"session-{index % 3}",
            )
            for index in range(250)
        ]
        await aadd_messagetables(messages, session)
        newest = [message.model_dump(mode="json") for message in reversed(messages)]
        return f"api/v1/monitor/{request.param}", params, newest


@pytest.mark.parametrize("order", ["ASC", "DESC"])
async def test_tied_timestamps_have_stable_nonoverlapping_pages(client, logged_in_headers, message_history, order):
    url, params, newest = message_history
    seen = []
    for offset in (0, 17, 34):
        response = await client.get(
            url, headers=logged_in_headers, params={**params, "limit": 17, "offset": offset, "order": order}
        )
        assert response.status_code == 200, response.text
        expected = newest[offset : offset + 17]
        if order == "ASC":
            expected = list(reversed(expected))
        ids = [message["id"] for message in response.json()]
        assert ids == [message["id"] for message in expected]
        seen.extend(ids)
    assert len(set(seen)) == 51


@pytest.mark.parametrize(
    ("query", "size", "offset"),
    [
        ({}, 100, 0),
        ({"limit": 0}, 100, 0),
        ({"limit": 1}, 1, 0),
        ({"limit": 200}, 200, 0),
        ({"limit": 100000}, 200, 0),
        ({"offset": 100}, 100, 100),
        ({"offset": 250}, 0, 250),
    ],
)
async def test_history_window_bounds(client, logged_in_headers, message_history, query, size, offset):
    url, params, newest = message_history
    response = await client.get(url, headers=logged_in_headers, params={**params, **query})
    assert response.status_code == 200, response.text
    assert len(response.json()) == size
    assert [message["id"] for message in response.json()] == [
        message["id"] for message in reversed(newest[offset : offset + size])
    ]


@pytest.mark.parametrize("order_by", ["sender", "sender_name", "session_id", "text"])
@pytest.mark.parametrize("order", ["ASC", "DESC"])
async def test_display_sort_preserves_newest_window(client, logged_in_headers, message_history, order_by, order):
    url, params, newest = message_history
    response = await client.get(
        url,
        headers=logged_in_headers,
        params={**params, "limit": 17, "offset": 100, "order_by": order_by, "order": order},
    )
    assert response.status_code == 200, response.text
    messages = response.json()
    assert {message["id"] for message in messages} == {message["id"] for message in newest[100:117]}
    values = [message[order_by] for message in messages]
    assert values == sorted(values, reverse=order == "DESC")


@pytest.mark.parametrize(
    ("query", "status"),
    [({"order": "invalid"}, 400), ({"order_by": "invalid"}, 400), ({"limit": -1}, 422), ({"offset": -1}, 422)],
)
async def test_invalid_pagination_parameters(client, logged_in_headers, message_history, query, status):
    url, params, _ = message_history
    response = await client.get(url, headers=logged_in_headers, params={**params, **query})
    assert response.status_code == status, response.text
