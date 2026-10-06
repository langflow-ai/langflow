from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.memory import aadd_messagetables
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from sqlalchemy import delete, update


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


@pytest.mark.parametrize("order", ["ASC", "DESC"])
@pytest.mark.parametrize("order_by", ["text", "timestamp"])
async def test_nullable_text_keeps_history_readable(client, logged_in_headers, message_history, order, order_by):
    """Legacy NULL text must survive both page sorting and response validation."""
    url, params, newest = message_history
    null_message_id = UUID(newest[0]["id"])
    async with session_scope() as session:
        await session.execute(update(MessageTable).where(MessageTable.id == null_message_id).values(text=None))

    response = await client.get(
        url,
        headers=logged_in_headers,
        params={**params, "limit": 3, "order_by": order_by, "order": order},
    )
    assert response.status_code == 200, response.text
    messages = response.json()
    assert len(messages) == 3
    assert next(message for message in messages if message["id"] == str(null_message_id))["text"] == ""
    if order_by == "text":
        expected = [newest[2]["id"], newest[1]["id"], newest[0]["id"]]
    else:
        expected = [message["id"] for message in reversed(newest[:3])]
    if order == "DESC":
        expected.reverse()
    assert [message["id"] for message in messages] == expected

    async with session_scope() as session:
        stored = await session.get(MessageTable, null_message_id)
        assert stored.text is None


def _cursor(row):
    """The cursor for the page below ``row``: its position as the API returned it."""
    return {"before_timestamp": row["timestamp"], "before_id": row["id"]}


async def _walk_with_cursor(client, headers, url, params, *, order, page_size):
    """Follow the cursor from page to page until a short page ends the history."""
    pages = []
    cursor = {}
    while True:
        response = await client.get(
            url, headers=headers, params={**params, **cursor, "limit": page_size, "order": order}
        )
        assert response.status_code == 200, response.text
        page = response.json()
        pages.append(page)
        if len(page) < page_size:
            return pages
        # The oldest row positions the next page: last when DESC, first when ASC.
        cursor = _cursor(page[-1 if order == "DESC" else 0])


@pytest.mark.parametrize("order", ["ASC", "DESC"])
async def test_cursor_walks_tied_timestamps_without_gaps_or_overlap(client, logged_in_headers, message_history, order):
    url, params, newest = message_history
    pages = await _walk_with_cursor(client, logged_in_headers, url, params, order=order, page_size=17)
    assert len(pages) == 15
    newest_first = [message["id"] for page in pages for message in (page if order == "DESC" else reversed(page))]
    assert newest_first == [message["id"] for message in newest]


@pytest.mark.parametrize("change", ["insert_newer", "delete_loaded"])
async def test_offset_pages_drift_when_history_changes_but_cursor_pages_do_not(
    client, logged_in_headers, message_history, change
):
    """Characterize why the history views page by cursor: offset counts rows from the newest one.

    A message arriving after the first page pushes the next offset window one row newer, so
    it repeats a row the client already has. Deleting a loaded message pulls the next window
    one row older, so it skips a row the client never sees. A cursor page starts below a fixed
    position and returns the same rows either way.
    """
    url, params, newest = message_history
    page = {**params, "limit": 20, "order": "DESC"}
    first = await client.get(url, headers=logged_in_headers, params=page)
    assert first.status_code == 200, first.text
    first_page = first.json()
    first_ids = [message["id"] for message in first_page]
    assert first_ids == [message["id"] for message in newest[:20]]

    async with session_scope() as session:
        if change == "insert_newer":
            await aadd_messagetables(
                [
                    MessageTable(
                        flow_id=UUID(newest[0]["flow_id"]),
                        files=[],
                        timestamp=datetime(2027, 1, 1, tzinfo=timezone.utc),
                        sender="User",
                        sender_name="Late",
                        text="Arrived between pages",
                        session_id="session-0",
                    )
                ],
                session,
            )
        else:
            await session.execute(delete(MessageTable).where(MessageTable.id == UUID(first_ids[5])))

    by_offset = await client.get(url, headers=logged_in_headers, params={**page, "offset": 20})
    by_cursor = await client.get(url, headers=logged_in_headers, params={**page, **_cursor(first_page[-1])})
    assert by_offset.status_code == 200, by_offset.text
    assert by_cursor.status_code == 200, by_cursor.text
    offset_ids = [message["id"] for message in by_offset.json()]
    cursor_ids = [message["id"] for message in by_cursor.json()]

    expected_next = [message["id"] for message in newest[20:40]]
    assert cursor_ids == expected_next
    if change == "insert_newer":
        # The oldest row of the first page comes back again.
        assert offset_ids == [first_ids[-1], *expected_next[:19]]
    else:
        # The row just below the first page is never returned.
        assert offset_ids == [*expected_next[1:], newest[40]["id"]]


async def test_cursor_page_is_unchanged_after_its_message_is_deleted(client, logged_in_headers, message_history):
    """The cursor carries a position, not a reference, so deleting that message changes nothing."""
    url, params, newest = message_history
    async with session_scope() as session:
        await session.execute(delete(MessageTable).where(MessageTable.id == UUID(newest[19]["id"])))

    response = await client.get(
        url, headers=logged_in_headers, params={**params, "limit": 20, "order": "DESC", **_cursor(newest[19])}
    )
    assert response.status_code == 200, response.text
    assert [message["id"] for message in response.json()] == [message["id"] for message in newest[20:40]]


async def test_cursor_timestamp_is_read_as_an_instant(client, logged_in_headers, message_history):
    """The same instant written with another UTC offset positions the same page."""
    url, params, newest = message_history
    anchor = newest[19]
    as_utc = datetime.strptime(anchor["timestamp"], "%Y-%m-%d %H:%M:%S.%f %Z").replace(tzinfo=timezone.utc)
    as_plus_two = as_utc.astimezone(timezone(timedelta(hours=2))).isoformat(timespec="microseconds")

    response = await client.get(
        url,
        headers=logged_in_headers,
        params={**params, "limit": 20, "order": "DESC", "before_timestamp": as_plus_two, "before_id": anchor["id"]},
    )
    assert response.status_code == 200, response.text
    assert [message["id"] for message in response.json()] == [message["id"] for message in newest[20:40]]


async def test_cursor_pages_within_the_filtered_session(client, logged_in_headers, message_history):
    url, params, newest = message_history
    session_rows = [message for message in newest if message["session_id"] == "session-1"]
    response = await client.get(
        url,
        headers=logged_in_headers,
        params={**params, "session_id": "session-1", "limit": 10, "order": "DESC", **_cursor(session_rows[9])},
    )
    assert response.status_code == 200, response.text
    assert [message["id"] for message in response.json()] == [message["id"] for message in session_rows[10:20]]


async def test_cursor_below_the_oldest_message_returns_an_empty_page(client, logged_in_headers, message_history):
    url, params, newest = message_history
    response = await client.get(url, headers=logged_in_headers, params={**params, **_cursor(newest[-1])})
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize("offset", [0, 20])
async def test_cursor_and_offset_are_mutually_exclusive(client, logged_in_headers, message_history, offset):
    url, params, newest = message_history
    response = await client.get(
        url, headers=logged_in_headers, params={**params, "offset": offset, **_cursor(newest[5])}
    )
    assert response.status_code == 400, response.text
    assert "offset" in response.json()["detail"]


@pytest.mark.parametrize(
    ("cursor", "status"),
    [
        ({"before_id": "<id>"}, 400),
        ({"before_timestamp": "<timestamp>"}, 400),
        ({"before_timestamp": "not-a-timestamp", "before_id": "<id>"}, 422),
        ({"before_timestamp": "<timestamp>", "before_id": "not-a-uuid"}, 422),
    ],
)
async def test_invalid_cursors_are_rejected(client, logged_in_headers, message_history, cursor, status):
    url, params, newest = message_history
    values = {"<id>": newest[5]["id"], "<timestamp>": newest[5]["timestamp"]}
    query = {key: values.get(value, value) for key, value in cursor.items()}
    response = await client.get(url, headers=logged_in_headers, params={**params, **query})
    assert response.status_code == status, response.text
