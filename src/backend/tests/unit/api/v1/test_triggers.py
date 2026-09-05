"""Route coverage for /api/v1/triggers.

Triggers carry no resource word of their own: they authorize on the flow they
fire. These tests pin that mapping — read for reads, write for management,
execute for replay/test — and the 404-not-403 existence rule for a caller who
cannot see the flow at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


def _payload(flow_id, **overrides) -> dict:
    body = {
        "flow_id": str(flow_id),
        "name": "weekday digest",
        "kind": "schedule",
        "config": {"cron": "0 8 * * 1-5", "timezone": "Europe/Lisbon"},
    }
    body.update(overrides)
    return body


async def _create(client: AsyncClient, headers: dict[str, str], flow_id, **overrides) -> dict:
    response = await client.post("api/v1/triggers", json=_payload(flow_id, **overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_owner_can_manage_a_trigger_end_to_end(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
) -> None:
    created = await _create(client, logged_in_headers, flow.id)
    assert created["state"] == "pending"
    assert created["binding_target"] == "flow"
    assert created["config"]["cron"] == "0 8 * * 1-5"

    listed = await client.get(f"api/v1/triggers?flow_id={flow.id}", headers=logged_in_headers)
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()] == [created["id"]]

    enabled = await client.post(f"api/v1/triggers/{created['id']}/enable", headers=logged_in_headers)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["state"] == "active"

    disabled = await client.post(f"api/v1/triggers/{created['id']}/disable", headers=logged_in_headers)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["state"] == "paused"

    patched = await client.patch(
        f"api/v1/triggers/{created['id']}",
        json={"name": "renamed", "concurrency_limit": 3},
        headers=logged_in_headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "renamed"
    assert patched.json()["concurrency_limit"] == 3

    deleted = await client.delete(f"api/v1/triggers/{created['id']}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text
    gone = await client.get(f"api/v1/triggers/{created['id']}", headers=logged_in_headers)
    assert gone.status_code == 404


async def test_a_trigger_on_someone_elses_flow_is_invisible(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
) -> None:
    """A trigger is visible exactly when its flow is; otherwise 404, never 403."""
    created = await _create(client, logged_in_headers, flow.id)

    async with session_scope() as session:
        stranger = User(
            username=f"stranger-{uuid4().hex[:8]}",
            password="hashed-not-used",  # noqa: S106  # pragma: allowlist secret
            is_active=True,
            is_superuser=False,
        )
        session.add(stranger)
        await session.flush()
        stranger_flow = Flow(name=f"stranger-flow-{uuid4().hex[:6]}", user_id=stranger.id)
        session.add(stranger_flow)
        await session.flush()
        stranger_trigger = Trigger(
            flow_id=stranger_flow.id,
            user_id=stranger.id,
            name="not yours",
            kind="schedule",
            config={},
            provider_state={},
            concurrency_limit=1,
            max_attempts=5,
        )
        session.add(stranger_trigger)
        await session.flush()
        stranger_flow_id, stranger_trigger_id = stranger_flow.id, stranger_trigger.id

    hidden = await client.get(f"api/v1/triggers/{stranger_trigger_id}", headers=logged_in_headers)
    assert hidden.status_code == 404, hidden.text

    listed = await client.get(f"api/v1/triggers?flow_id={stranger_flow_id}", headers=logged_in_headers)
    assert listed.status_code == 404, listed.text

    created_on_stranger_flow = await client.post(
        "api/v1/triggers", json=_payload(stranger_flow_id), headers=logged_in_headers
    )
    assert created_on_stranger_flow.status_code == 404, created_on_stranger_flow.text

    deleted = await client.delete(f"api/v1/triggers/{stranger_trigger_id}", headers=logged_in_headers)
    assert deleted.status_code == 404, deleted.text

    # The caller's own trigger is unaffected.
    mine = await client.get(f"api/v1/triggers/{created['id']}", headers=logged_in_headers)
    assert mine.status_code == 200, mine.text


async def test_unknown_trigger_and_unknown_flow_are_404(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    missing = await client.get(f"api/v1/triggers/{uuid4()}", headers=logged_in_headers)
    assert missing.status_code == 404
    created = await client.post("api/v1/triggers", json=_payload(uuid4()), headers=logged_in_headers)
    assert created.status_code == 404


async def test_pin_requires_a_version_of_the_same_flow(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    active_user,
    flow,
) -> None:
    created = await _create(client, logged_in_headers, flow.id)

    async with session_scope() as session:
        other_flow = Flow(name=f"other-{uuid4().hex[:6]}", user_id=active_user.id)
        session.add(other_flow)
        await session.flush()
        own_version = FlowVersion(flow_id=flow.id, user_id=active_user.id, data={"nodes": []}, version_number=1)
        foreign_version = FlowVersion(
            flow_id=other_flow.id, user_id=active_user.id, data={"nodes": []}, version_number=1
        )
        session.add(own_version)
        session.add(foreign_version)
        await session.flush()
        own_version_id, foreign_version_id = own_version.id, foreign_version.id

    rejected = await client.post(
        f"api/v1/triggers/{created['id']}/pin",
        json={"flow_version_id": str(foreign_version_id)},
        headers=logged_in_headers,
    )
    assert rejected.status_code == 404, rejected.text

    pinned = await client.post(
        f"api/v1/triggers/{created['id']}/pin",
        json={"flow_version_id": str(own_version_id)},
        headers=logged_in_headers,
    )
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["flow_version_id"] == str(own_version_id)

    unpinned = await client.post(
        f"api/v1/triggers/{created['id']}/pin",
        json={"flow_version_id": None},
        headers=logged_in_headers,
    )
    assert unpinned.status_code == 200, unpinned.text
    assert unpinned.json()["flow_version_id"] is None


async def test_test_and_replay_write_linked_ledger_rows(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
) -> None:
    """Replay writes a NEW row linked to the original; it never rewinds history."""
    created = await _create(client, logged_in_headers, flow.id)

    fired = await client.post(
        f"api/v1/triggers/{created['id']}/test", json={"payload": {"hello": "world"}}, headers=logged_in_headers
    )
    assert fired.status_code == 202, fired.text
    event = fired.json()
    assert event["state"] == "pending"
    assert event["payload"] == {"test": True, "hello": "world"}

    replayed = await client.post(
        f"api/v1/triggers/{created['id']}/replay",
        json={"event_id": event["id"]},
        headers=logged_in_headers,
    )
    assert replayed.status_code == 202, replayed.text
    assert replayed.json()["replay_of_event_id"] == event["id"]
    assert replayed.json()["id"] != event["id"]

    # A second replay of the same event is a second distinct row, not a conflict.
    again = await client.post(
        f"api/v1/triggers/{created['id']}/replay",
        json={"event_id": event["id"]},
        headers=logged_in_headers,
    )
    assert again.status_code == 202, again.text
    assert again.json()["id"] not in {event["id"], replayed.json()["id"]}

    events = await client.get(f"api/v1/triggers/{created['id']}/events", headers=logged_in_headers)
    assert events.status_code == 200, events.text
    assert len(events.json()) == 3


async def test_replaying_an_event_from_another_trigger_is_404(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
) -> None:
    """Ledger rows are addressed through their trigger, never by id alone."""
    first = await _create(client, logged_in_headers, flow.id, name="first")
    second = await _create(client, logged_in_headers, flow.id, name="second")

    fired = await client.post(f"api/v1/triggers/{first['id']}/test", json={}, headers=logged_in_headers)
    assert fired.status_code == 202, fired.text

    crossed = await client.post(
        f"api/v1/triggers/{second['id']}/replay",
        json={"event_id": fired.json()["id"]},
        headers=logged_in_headers,
    )
    assert crossed.status_code == 404, crossed.text


async def test_deployment_binding_requires_a_deployment_id(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
) -> None:
    response = await client.post(
        "api/v1/triggers",
        json=_payload(flow.id, binding_target="deployment"),
        headers=logged_in_headers,
    )
    assert response.status_code == 422, response.text


async def test_trigger_kind_must_match_the_registry_grammar(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
) -> None:
    """The kind is a registry key across planes, so whitespace and case are rejected."""
    for bad_kind in ("Schedule", "sched ule", " schedule"):
        response = await client.post(
            "api/v1/triggers", json=_payload(flow.id, kind=bad_kind), headers=logged_in_headers
        )
        assert response.status_code == 422, f"{bad_kind!r} was accepted: {response.text}"


async def test_a_trigger_created_through_the_api_is_owned_by_the_flow_owner(
    client: AsyncClient,  # noqa: ARG001
    active_user,
    monkeypatch,
) -> None:
    """Identity comes from the flow, never from whoever called the route.

    A trigger run executes as ``flow_owner`` and flow-save reconciliation
    already creates rows that way. Under an authorization plugin a collaborator
    with flow write can reach this route on somebody else's flow; keying the row
    off the caller would give that flow two kinds of trigger identity and would
    resolve the *collaborator's* connections for unattended runs.

    The cross-owner read is only reachable with the authorization plugin
    installed (OSS ``_read_flow`` is owner-scoped), so the fetch is stubbed and
    the route function is called directly — the mapping under test is what the
    route does with the flow it was given.
    """
    from langflow.api.v1 import triggers as triggers_route
    from langflow.services.database.models.trigger.schemas import TriggerCreate
    from langflow.services.deps import get_trigger_service

    async with session_scope() as session:
        owner = User(
            username=f"flow-owner-{uuid4().hex[:8]}",
            password="hashed-not-used",  # noqa: S106  # pragma: allowlist secret
            is_active=True,
        )
        session.add(owner)
        await session.flush()
        owner_flow = Flow(name=f"owned-{uuid4().hex[:6]}", user_id=owner.id)
        session.add(owner_flow)
        await session.flush()
        owner_id, owner_flow_id = owner.id, owner_flow.id

    async def _stub_authorized_flow(session, user, flow_id, action):  # noqa: ARG001
        return await session.get(Flow, flow_id)

    monkeypatch.setattr(triggers_route, "_authorized_flow", _stub_authorized_flow)

    async with session_scope() as session:
        created = await triggers_route.create_trigger(
            payload=TriggerCreate(flow_id=owner_flow_id, name="collaborator armed this", kind="schedule"),
            session=session,
            current_user=active_user,
            service=get_trigger_service(),
        )

    assert created.user_id == owner_id
    assert created.user_id != active_user.id
