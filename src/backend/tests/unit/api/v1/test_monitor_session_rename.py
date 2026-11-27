"""Session renames preserve message responses without per-message reads."""

import re
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.schema.message import MessageResponse
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_db_service, session_scope
from sqlalchemy import event
from sqlmodel import select


@pytest.fixture(params=["ordinary", "shared"])
def rename_route(request):
    source_flow_id = uuid4()
    shared = request.param == "shared"
    return {
        "shared": shared,
        "source_flow_id": source_flow_id,
        "path": f"api/v1/monitor/messages/{'shared/' if shared else ''}session/old-session",
        "params": {"new_session_id": "new-session", **({"source_flow_id": str(source_flow_id)} if shared else {})},
    }


@pytest.fixture
async def rename_messages(active_user, rename_route):
    """Seed owned and foreign sessions using the real ownership queries."""
    async with session_scope() as session:
        other_user = User(username=f"rename-other-{uuid4()}", password="unused")  # noqa: S106
        session.add(other_user)
        await session.flush()
        owned_flow = Flow(name="rename-owned", user_id=active_user.id)
        foreign_flow = Flow(name="rename-foreign", user_id=other_user.id)
        other_flow = Flow(name="rename-other-flow", user_id=active_user.id)
        session.add_all([owned_flow, foreign_flow, other_flow])
        await session.flush()
        if rename_route["shared"]:
            owned_flow_id = compute_virtual_flow_id(
                active_user.id, rename_route["source_flow_id"], principal_type="user"
            )
            foreign_flow_id = compute_virtual_flow_id(
                other_user.id, rename_route["source_flow_id"], principal_type="user"
            )
            other_flow_id = compute_virtual_flow_id(active_user.id, other_flow.id, principal_type="user")
        else:
            owned_flow_id, foreign_flow_id, other_flow_id = owned_flow.id, foreign_flow.id, other_flow.id

        def message(flow_id, session_id, index):
            return MessageTable(
                flow_id=flow_id,
                session_id=session_id,
                text=f"Message {index}",
                sender="User" if index % 2 == 0 else "Machine",
                sender_name="User" if index % 2 == 0 else "AI",
                timestamp=datetime(2026, 1, 1, 0, 0, index, 123456, tzinfo=timezone.utc),
                context_id="rename-context",
                files=["attachment.txt"],
                edit=index % 2 == 0,
                properties={"positive_feedback": True},
                category="message",
                content_blocks=[{"title": "Details", "contents": [{"type": "text", "text": "Preserved content"}]}],
                session_metadata={"tag": "preserved"},
            )

        owned = [message(owned_flow_id, "old-session", i) for i in range(8)]
        # Ordinary sessions may span multiple owned flows; shared sessions may not.
        if not rename_route["shared"]:
            owned[-1].flow_id = other_flow_id
        untouched = [
            message(foreign_flow_id, "old-session", 10),
            message(owned_flow_id, "other-session", 11),
        ]
        if rename_route["shared"]:
            untouched.append(message(other_flow_id, "old-session", 12))
        session.add_all([*owned, *untouched])
        await session.flush()
        return {"owned": [row.id for row in owned], "untouched": [row.id for row in untouched]}


async def _stored_responses():
    async with session_scope() as session:
        rows = (await session.exec(select(MessageTable))).all()
        return {
            str(row.id): MessageResponse.model_validate(row, from_attributes=True).model_dump(mode="json")
            for row in rows
        }


@contextmanager
def _record_message_selects():
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        if re.match(r"\s*SELECT\b", statement, re.IGNORECASE) and re.search(
            r'\bFROM\s+"?message"?\b', statement, re.IGNORECASE
        ):
            statements.append(statement)

    engine = get_db_service().engine.sync_engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


@pytest.mark.parametrize("message_count", [1, 8])
async def test_rename_session_uses_one_message_select(
    client, logged_in_headers, rename_route, rename_messages, message_count
):
    async with session_scope() as session:
        for message_id in rename_messages["owned"][message_count:]:
            await session.delete(await session.get(MessageTable, message_id))
    before = await _stored_responses()
    owned_ids = {str(message_id) for message_id in rename_messages["owned"][:message_count]}
    expected = [before[message_id] | {"session_id": "new-session"} for message_id in owned_ids]

    with _record_message_selects() as statements:
        response = await client.patch(rename_route["path"], params=rename_route["params"], headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert sorted(response.json(), key=lambda row: row["id"]) == sorted(expected, key=lambda row: row["id"])
    after = await _stored_responses()
    assert after == {
        message_id: row | {"session_id": "new-session"} if message_id in owned_ids else row
        for message_id, row in before.items()
    }
    assert len(statements) == 1, statements


@pytest.mark.parametrize("foreign_only", [False, True])
async def test_rename_missing_or_foreign_session_returns_404(
    client, logged_in_headers, rename_route, rename_messages, foreign_only
):
    async with session_scope() as session:
        for message_id in rename_messages["owned"]:
            await session.delete(await session.get(MessageTable, message_id))
    path = rename_route["path"] if foreign_only else rename_route["path"].replace("old-session", "missing-session")
    before = await _stored_responses()
    response = await client.patch(path, params=rename_route["params"], headers=logged_in_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "No messages found with the given session ID"}
    assert await _stored_responses() == before


async def test_rename_session_requires_auth(client, rename_route):
    response = await client.patch(rename_route["path"], params=rename_route["params"])
    assert response.status_code == 403


@pytest.mark.usefixtures("rename_messages")
async def test_rename_session_rolls_back_on_flush_failure(client, logged_in_headers, rename_route):
    before = await _stored_responses()

    def fail_after_update(_conn, _cursor, statement, _parameters, _context, _executemany):
        if re.match(r'\s*UPDATE\s+"?message"?\b', statement, re.IGNORECASE):
            msg = "Injected message update failure"
            raise RuntimeError(msg)

    engine = get_db_service().engine.sync_engine
    event.listen(engine, "after_cursor_execute", fail_after_update)
    try:
        response = await client.patch(rename_route["path"], params=rename_route["params"], headers=logged_in_headers)
    finally:
        event.remove(engine, "after_cursor_execute", fail_after_update)
    assert response.status_code == 500
    assert await _stored_responses() == before
