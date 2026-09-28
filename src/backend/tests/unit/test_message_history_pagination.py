from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.api.v1.monitor import _read_history_window
from langflow.memory import aadd_messagetables
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from sqlalchemy import delete, update
from sqlmodel import select


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


async def _walk_with_cursor(client, headers, url, params, *, order, page_size):
    """Follow before_id from page to page until a short page ends the history."""
    pages = []
    before_id = None
    while True:
        cursor = {"before_id": before_id} if before_id else {}
        response = await client.get(
            url, headers=headers, params={**params, **cursor, "limit": page_size, "order": order}
        )
        assert response.status_code == 200, response.text
        page = response.json()
        pages.append(page)
        if len(page) < page_size:
            return pages
        # The oldest row anchors the next page: last when DESC, first when ASC.
        before_id = page[-1 if order == "DESC" else 0]["id"]


@pytest.mark.parametrize("order", ["ASC", "DESC"])
async def test_before_id_walks_tied_timestamps_without_gaps_or_overlap(
    client, logged_in_headers, message_history, order
):
    url, params, newest = message_history
    pages = await _walk_with_cursor(client, logged_in_headers, url, params, order=order, page_size=17)
    assert len(pages) == 15
    newest_first = [message["id"] for page in pages for message in (page if order == "DESC" else reversed(page))]
    assert newest_first == [message["id"] for message in newest]


@pytest.mark.parametrize("change", ["insert_newer", "delete_loaded"])
async def test_offset_pages_drift_when_history_changes_but_before_id_pages_do_not(
    client, logged_in_headers, message_history, change
):
    """Characterize why the chat views page by cursor: offset counts rows from the newest one.

    A message arriving after the first page pushes the next offset window one row newer, so
    it repeats a row the client already has. Deleting a loaded message pulls the next window
    one row older, so it skips a row the client never sees. A before_id page starts from a
    specific message and returns the same rows either way.
    """
    url, params, newest = message_history
    page = {**params, "limit": 20, "order": "DESC"}
    first = await client.get(url, headers=logged_in_headers, params=page)
    assert first.status_code == 200, first.text
    first_ids = [message["id"] for message in first.json()]
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
    by_cursor = await client.get(url, headers=logged_in_headers, params={**page, "before_id": first_ids[-1]})
    assert by_offset.status_code == 200, by_offset.text
    assert by_cursor.status_code == 200, by_cursor.text
    offset_ids = [message["id"] for message in by_offset.json()]
    cursor_ids = [message["id"] for message in by_cursor.json()]

    expected_next = [message["id"] for message in newest[20:40]]
    assert cursor_ids == expected_next
    if change == "insert_newer":
        # The oldest row of the first page comes back again.
        assert offset_ids[0] == first_ids[-1]
        assert offset_ids == [first_ids[-1], *expected_next[:19]]
    else:
        # The row just below the first page is never returned.
        assert expected_next[0] not in offset_ids
        assert offset_ids == [*expected_next[1:], newest[40]["id"]]


async def test_before_id_page_survives_the_anchor_being_deleted_mid_request(message_history, monkeypatch):
    """A delete landing between the anchor check and the page query must not empty the page.

    An empty page reads as the end of history, so a client would stop loading older messages.
    """
    _, _, newest = message_history
    anchor_id = UUID(newest[19]["id"])
    async with session_scope() as session:
        original_exec = session.exec
        statements = 0

        async def exec_then_delete_anchor(statement, *args, **kwargs):
            nonlocal statements
            result = await original_exec(statement, *args, **kwargs)
            statements += 1
            if statements == 1:
                await session.execute(delete(MessageTable).where(MessageTable.id == anchor_id))
            return result

        monkeypatch.setattr(session, "exec", exec_then_delete_anchor)
        page = await _read_history_window(
            session,
            select(MessageTable).where(MessageTable.flow_id == UUID(newest[0]["flow_id"])),
            order_by="timestamp",
            order="DESC",
            limit=20,
            offset=None,
            before_id=anchor_id,
        )

    assert statements == 2
    assert [str(message.id) for message in page] == [message["id"] for message in newest[20:40]]


async def test_before_id_pages_within_the_filtered_session(client, logged_in_headers, message_history):
    url, params, newest = message_history
    session_rows = [message for message in newest if message["session_id"] == "session-1"]
    response = await client.get(
        url,
        headers=logged_in_headers,
        params={**params, "session_id": "session-1", "limit": 10, "order": "DESC", "before_id": session_rows[9]["id"]},
    )
    assert response.status_code == 200, response.text
    assert [message["id"] for message in response.json()] == [message["id"] for message in session_rows[10:20]]


async def test_before_id_on_the_oldest_message_returns_an_empty_page(client, logged_in_headers, message_history):
    url, params, newest = message_history
    response = await client.get(url, headers=logged_in_headers, params={**params, "before_id": newest[-1]["id"]})
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize("offset", [0, 20])
async def test_before_id_and_offset_are_mutually_exclusive(client, logged_in_headers, message_history, offset):
    url, params, newest = message_history
    response = await client.get(
        url, headers=logged_in_headers, params={**params, "offset": offset, "before_id": newest[5]["id"]}
    )
    assert response.status_code == 400, response.text
    assert "offset" in response.json()["detail"]


async def test_before_id_outside_the_filtered_history_is_rejected(client, logged_in_headers, message_history):
    """A missing anchor must not read as an empty page, which would look like the end of history."""
    url, params, newest = message_history
    other_session = next(message for message in newest if message["session_id"] == "session-2")
    cases = [
        {"before_id": str(uuid4())},
        {"before_id": "not-a-uuid"},
        {"before_id": other_session["id"], "session_id": "session-1"},
    ]
    statuses = []
    for query in cases:
        response = await client.get(url, headers=logged_in_headers, params={**params, **query})
        statuses.append(response.status_code)
    assert statuses == [400, 422, 400]
