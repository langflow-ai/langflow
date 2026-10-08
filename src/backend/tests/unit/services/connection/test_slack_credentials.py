"""Manually entered Slack tokens, and the app-level token's confinement.

The app-level token (``xapp-``) exists to open Slack Socket Mode sockets and for
nothing else. These tests pin the three rules that keep it that way: its marker
is written by the server and cannot be forged onto another token, it is refused
where Socket Mode cannot run, and it resolves only inside the listener process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from langflow.services.database.models.connection import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal

from tests.unit.services.triggers import slack_fixtures as fx

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

APP_TOKEN = "xapp-1-A0APP00001-2222-created"  # noqa: S105  # pragma: allowlist secret
BOT_TOKEN = "xoxb-1111-2222-created"  # noqa: S105  # pragma: allowlist secret


def _body(token: str, **overrides) -> dict:
    body = {
        "provider_key": "slack",
        "name": "socket_app",
        "display_name": "Slack app-level token",
        "executing_identity": {"identity": "bot"},
        "allow_non_interactive": True,
        "granted_scopes": [],
        "credentials": {"access_token": token},
    }
    body.update(overrides)
    return body


async def _row(connection_id: str) -> Connection:
    async with session_scope() as session:
        return await session.get(Connection, UUID(connection_id))


@pytest.fixture
def listener_process(active_user, monkeypatch):  # noqa: ARG001 - the API app must exist before the flag is set
    """Play the listener process: ``create_app`` refuses to run once the flag is set."""
    from langflow.services.triggers.listeners import guard

    monkeypatch.setattr(guard, "_IS_LISTENER_PROCESS", True)


def _request(row: Connection, *, user_id) -> ConnectionResolutionRequest:
    return ConnectionResolutionRequest(
        ref=ConnectionRef(provider=row.provider_key, name=row.name),
        principal=ExecutionPrincipal(kind="flow_owner", user_id=str(user_id), interactive=False),
    )


# --------------------------------------------------------------------------- #
# Creating the connection
# --------------------------------------------------------------------------- #


async def test_an_app_level_token_is_stored_with_a_server_set_marker(
    client: AsyncClient, logged_in_headers: dict[str, str]
) -> None:
    response = await client.post(
        "api/v1/connections", json=_body(APP_TOKEN, granted_scopes=["chat:write"]), headers=logged_in_headers
    )

    assert response.status_code == 201, response.text
    assert response.json()["granted_scopes"] == ["connections:write"], "the client never chooses this marker"
    assert (await _row(response.json()["id"])).granted_scopes == ["connections:write"]


async def test_a_bot_token_cannot_claim_the_app_level_marker(
    client: AsyncClient, logged_in_headers: dict[str, str]
) -> None:
    forged = await client.post(
        "api/v1/connections",
        json=_body(BOT_TOKEN, name="forged", granted_scopes=["chat:write", "connections:write"]),
        headers=logged_in_headers,
    )
    assert forged.status_code == 422, forged.text

    honest = await client.post(
        "api/v1/connections",
        json=_body(BOT_TOKEN, name="bot_token", granted_scopes=["chat:write", "reactions:write"]),
        headers=logged_in_headers,
    )
    assert honest.status_code == 201, honest.text
    assert honest.json()["granted_scopes"] == ["chat:write", "reactions:write"]


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"executing_identity": {"identity": "user_delegated"}}, "identity must be 'bot'"),
        ({"credentials": {"access_token": APP_TOKEN, "refresh_token": "r"}}, "neither expire nor refresh"),
        ({"credentials": {"access_token": APP_TOKEN, "expires_at": "2030-01-01T00:00:00Z"}}, "neither expire"),
    ],
)
async def test_an_app_level_token_is_refused_in_shapes_it_never_has(
    client: AsyncClient, logged_in_headers: dict[str, str], overrides: dict, fragment: str
) -> None:
    response = await client.post("api/v1/connections", json=_body(APP_TOKEN, **overrides), headers=logged_in_headers)

    assert response.status_code == 422, response.text
    assert fragment in response.json()["detail"]


async def test_an_app_level_token_is_refused_on_hosted(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch
) -> None:
    """Hosted serves every tenant from a Marketplace app, and those cannot use Socket Mode."""
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "hosted")

    response = await client.post("api/v1/connections", json=_body(APP_TOKEN), headers=logged_in_headers)

    assert response.status_code == 422, response.text
    assert "Events API" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Resolving it
# --------------------------------------------------------------------------- #


async def test_an_app_level_token_never_resolves_outside_the_listener(active_user) -> None:
    connection_id = await fx.make_app_token_connection(active_user.id)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)

    with pytest.raises(ConnectionNotAuthorizedError) as refused:
        await get_connection_resolver_service().resolve(_request(row, user_id=active_user.id))

    assert refused.value.reason == "listener-only"


@pytest.mark.usefixtures("listener_process")
async def test_the_listener_resolves_an_app_level_token(active_user) -> None:
    connection_id = await fx.make_app_token_connection(active_user.id)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)

    credential = await get_connection_resolver_service().resolve(_request(row, user_id=active_user.id))

    assert credential.access_token.get_secret_value() == fx.APP_TOKEN


async def test_an_app_level_token_without_its_marker_is_still_confined(active_user) -> None:
    """The prefix is checked after decryption too, so a row written some other way is caught."""
    connection_id = await fx.make_app_token_connection(active_user.id)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        row.granted_scopes = []
        session.add(row)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)

    with pytest.raises(ConnectionNotAuthorizedError):
        await get_connection_resolver_service().resolve(_request(row, user_id=active_user.id))


async def test_a_health_check_does_not_mark_an_app_level_token_unhealthy(active_user) -> None:
    connection_id = await fx.make_app_token_connection(active_user.id)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        result = await get_connection_resolver_service().check_health(
            session,
            row=row,
            principal=ExecutionPrincipal(kind="flow_owner", user_id=str(active_user.id), interactive=True),
        )

    assert result.status == "ready"
    assert result.health == "unknown"


async def test_a_socket_mode_trigger_passes_dispatch_preflight_in_the_api_process(active_user, flow) -> None:
    """Preflight reads the connection's metadata, never its secret, so confinement cannot block a run."""
    from langflow.services.triggers.principal import connection_preflight

    connection_id = await fx.make_app_token_connection(active_user.id)
    trigger_id = await fx.arm(flow.id, active_user.id, connection_id, mechanism="slack.socket_mode")
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert await connection_preflight(session, trigger) is None
