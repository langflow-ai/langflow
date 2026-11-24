"""A trigger may only name a connection its owner owns.

A provider trigger turns its connection into a stream of that account's data and
writes it where the trigger's flow readers can see it. These tests pin the
ownership rule at the owner API: a colleague's connection and an instance
connection are both refused, and the provider kinds whose connection comes from
a canvas node cannot be written through the API at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


def _payload(flow_id, **overrides) -> dict:
    body = {
        "flow_id": str(flow_id),
        "name": "digest",
        "kind": "schedule",
        "config": {"cron": "0 8 * * 1-5", "timezone": "UTC"},
    }
    body.update(overrides)
    return body


async def _connection(*, owner_id: UUID | None, instance: bool = False) -> UUID:
    async with session_scope() as session:
        row = Connection(
            provider_key="slack",
            name=f"conn_{uuid4().hex[:8]}",
            display_name="Slack",
            ownership_mode="instance" if instance else "user",
            owner_id=None if instance else owner_id,
            status="ready",
            allow_non_interactive=True,
        )
        session.add(row)
        await session.flush()
        return row.id


async def _stranger() -> UUID:
    async with session_scope() as session:
        user = User(
            username=f"stranger-{uuid4().hex[:8]}",
            password="hashed-not-used",  # noqa: S106  # pragma: allowlist secret
            is_active=True,
        )
        session.add(user)
        await session.flush()
        return user.id


async def test_a_trigger_can_use_its_owners_own_connection(
    client: AsyncClient, logged_in_headers: dict[str, str], flow, active_user
) -> None:
    connection_id = await _connection(owner_id=active_user.id)
    response = await client.post(
        "api/v1/triggers", json=_payload(flow.id, connection_id=str(connection_id)), headers=logged_in_headers
    )
    assert response.status_code == 201, response.text
    assert response.json()["connection_id"] == str(connection_id)


@pytest.mark.parametrize("shape", ["someone_else", "instance", "missing"])
async def test_a_trigger_cannot_be_created_on_a_connection_its_owner_does_not_own(
    client: AsyncClient, logged_in_headers: dict[str, str], flow, shape: str
) -> None:
    if shape == "someone_else":
        connection_id = await _connection(owner_id=await _stranger())
    elif shape == "instance":
        connection_id = await _connection(owner_id=None, instance=True)
    else:
        connection_id = uuid4()

    response = await client.post(
        "api/v1/triggers", json=_payload(flow.id, connection_id=str(connection_id)), headers=logged_in_headers
    )

    assert response.status_code == 422, response.text
    # One answer for "not yours" and "does not exist": no oracle for foreign ids.
    assert "connection its owner owns" in response.json()["detail"]


async def test_a_trigger_cannot_be_repointed_at_someone_elses_connection(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    created = await client.post("api/v1/triggers", json=_payload(flow.id), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    foreign = await _connection(owner_id=await _stranger())

    response = await client.patch(
        f"api/v1/triggers/{created.json()['id']}", json={"connection_id": str(foreign)}, headers=logged_in_headers
    )

    assert response.status_code == 422, response.text
    async with session_scope() as session:
        row = await session.get(Trigger, UUID(created.json()["id"]))
        assert row.connection_id is None


@pytest.mark.parametrize("kind", ["slack.message", "slack.reaction"])
async def test_canvas_only_kinds_cannot_be_created_through_the_api(
    client: AsyncClient, logged_in_headers: dict[str, str], flow, kind: str
) -> None:
    """Only flow-save reconciliation writes a Slack trigger: it is what normalizes the config."""
    response = await client.post(
        "api/v1/triggers",
        json=_payload(flow.id, kind=kind, provider="slack", config={}),
        headers=logged_in_headers,
    )
    assert response.status_code == 422, response.text


async def test_the_mechanism_is_never_client_supplied(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    created = await client.post(
        "api/v1/triggers",
        json=_payload(flow.id, config={"cron": "0 8 * * *", "mechanism_id": "slack.socket_mode"}),
        headers=logged_in_headers,
    )
    assert created.status_code == 422, created.text

    ok = await client.post("api/v1/triggers", json=_payload(flow.id), headers=logged_in_headers)
    assert ok.status_code == 201, ok.text
    patched = await client.patch(
        f"api/v1/triggers/{ok.json()['id']}",
        json={"config": {"cron": "0 9 * * *", "mechanism_id": "slack.events_api"}},
        headers=logged_in_headers,
    )
    assert patched.status_code == 422, patched.text


async def test_a_canvas_only_triggers_config_and_connection_are_not_editable_through_the_api(
    client: AsyncClient, logged_in_headers: dict[str, str], flow, active_user
) -> None:
    connection_id = await _connection(owner_id=active_user.id)
    async with session_scope() as session:
        row = Trigger(
            flow_id=flow.id,
            user_id=active_user.id,
            name="On Message",
            kind="slack.message",
            provider="slack",
            node_id="SlackOnMessage-abc",
            connection_id=connection_id,
            config={"mechanism_id": "slack.socket_mode"},
            provider_state={},
            concurrency_limit=1,
            max_attempts=5,
        )
        session.add(row)
        await session.flush()
        trigger_id = row.id

    for body in ({"config": {}}, {"connection_id": None}):
        response = await client.patch(f"api/v1/triggers/{trigger_id}", json=body, headers=logged_in_headers)
        assert response.status_code == 422, (body, response.text)

    renamed = await client.patch(f"api/v1/triggers/{trigger_id}", json={"name": "renamed"}, headers=logged_in_headers)
    assert renamed.status_code == 200, renamed.text
