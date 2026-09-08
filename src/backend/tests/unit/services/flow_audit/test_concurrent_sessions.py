"""Whose session is it, when more than one person is editing inside the same window."""

import uuid
from datetime import datetime, timezone

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_audit.model import FlowAuditEntry
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_audit.recorder import SOURCE_EDITOR, SOURCE_OVERWRITE, record_flow_edit
from sqlmodel import col, desc, select


@pytest.fixture
def audit_on():
    settings = get_settings_service().settings
    previous = settings.flow_audit_enabled
    settings.flow_audit_enabled = True
    yield settings
    settings.flow_audit_enabled = previous


def graph(value: str) -> dict:
    return {
        "nodes": [
            {
                "id": "n0",
                "position": {"x": 0, "y": 0},
                "data": {
                    "id": "n0",
                    "node": {"display_name": "Chat Input", "template": {"f": {"display_name": "f", "value": value}}},
                },
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def _seed_flow(session, user_id) -> Flow:
    flow = Flow(
        name=f"sessions-{uuid.uuid4()}",
        data=graph("start"),
        user_id=user_id,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow


async def _entries(session, flow_id):
    statement = (
        select(FlowAuditEntry).where(FlowAuditEntry.flow_id == flow_id).order_by(desc(col(FlowAuditEntry.updated_at)))
    )
    return (await session.exec(statement)).all()


async def test_two_people_editing_in_one_window_get_one_session_each(client, active_user, audit_on):  # noqa: ARG001
    """The session is keyed by person, so concurrent editors never share a row."""
    alice = active_user.id
    bob = uuid.uuid4()

    async with session_scope() as session:
        flow = await _seed_flow(session, alice)

        await record_flow_edit(
            session,
            flow_id=flow.id,
            user_id=alice,
            before=graph("start"),
            after=graph("alice-1"),
            source=SOURCE_EDITOR,
        )
        await record_flow_edit(
            session,
            flow_id=flow.id,
            user_id=bob,
            before=graph("alice-1"),
            after=graph("bob-1"),
            source=SOURCE_EDITOR,
        )
        # Both keep going inside the same window.
        await record_flow_edit(
            session,
            flow_id=flow.id,
            user_id=alice,
            before=graph("bob-1"),
            after=graph("alice-2"),
            source=SOURCE_EDITOR,
        )
        await session.commit()

        entries = await _entries(session, flow.id)

    assert len(entries) == 2, "one session per person, not one per flow"
    assert {entry.user_id for entry in entries} == {alice, bob}


async def test_one_person_in_two_tabs_stays_a_single_session(client, active_user, audit_on):  # noqa: ARG001
    """Two tabs are still one person having one sitting."""
    async with session_scope() as session:
        flow = await _seed_flow(session, active_user.id)

        for value in ("tab-a", "tab-b", "tab-a-again"):
            await record_flow_edit(
                session,
                flow_id=flow.id,
                user_id=active_user.id,
                before=graph("start"),
                after=graph(value),
                source=SOURCE_EDITOR,
            )
        await session.commit()

        entries = await _entries(session, flow.id)

    assert len(entries) == 1


async def test_a_resolved_conflict_never_folds_into_the_other_persons_session(client, active_user, audit_on):
    """Bob resolving with Update flow is his own act, not a line in Alice's session."""
    alice = active_user.id
    bob = uuid.uuid4()

    async with session_scope() as session:
        flow = await _seed_flow(session, alice)

        await record_flow_edit(
            session,
            flow_id=flow.id,
            user_id=alice,
            before=graph("start"),
            after=graph("alice"),
            source=SOURCE_EDITOR,
        )
        await record_flow_edit(
            session,
            flow_id=flow.id,
            user_id=bob,
            before=graph("alice"),
            after=graph("bob-merged"),
            source=SOURCE_OVERWRITE,
        )
        await session.commit()

        entries = await _entries(session, flow.id)

    assert len(entries) == 2
    by_user = {entry.user_id: entry.source for entry in entries}
    assert by_user[alice] == SOURCE_EDITOR
    assert by_user[bob] == SOURCE_OVERWRITE
