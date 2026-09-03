"""API coverage for connection ownership and secret-safe serialization."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.auth.utils import get_auth_service
from langflow.services.database.models.connection import ConnectionSecret
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import ConnectionNotAuthorizedError, ScopeMissingError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal
from sqlmodel import select

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


def _payload(
    *,
    ownership_mode: str = "user",
    name: str = "work",
    allow_non_interactive: bool = False,
) -> dict:
    return {
        "provider_key": "google_workspace",
        "name": name,
        "display_name": "Work Google",
        "ownership_mode": ownership_mode,
        "granted_scopes": ["calendar.readonly"],
        "executing_identity": {
            "identity": "user_delegated",
            "account": {"id": "account-123", "display": "Work", "tenant_id": "tenant-123"},
        },
        "allow_non_interactive": allow_non_interactive,
        "credentials": {
            "access_token": "access-token-do-not-return",
            "refresh_token": "refresh-token-do-not-return",
            "token_type": "Bearer",
        },
    }


def _assert_no_credentials(value: object) -> None:
    forbidden_keys = {"access_token", "refresh_token", "encrypted_payload", "credentials"}
    if isinstance(value, dict):
        assert forbidden_keys.isdisjoint(value)
        for item in value.values():
            _assert_no_credentials(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_credentials(item)
    elif isinstance(value, str):
        assert value not in {"access-token-do-not-return", "refresh-token-do-not-return"}


@pytest.mark.usefixtures("active_user")
async def test_connection_responses_never_include_tokens(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["has_credentials"] is True
    assert body["status"] == "ready"
    _assert_no_credentials(body)

    listed = await client.get("api/v1/connections", headers=logged_in_headers)
    assert listed.status_code == 200, listed.text
    _assert_no_credentials(listed.json())

    filtered = await client.get("api/v1/connections?provider=google_workspace", headers=logged_in_headers)
    assert filtered.status_code == 200, filtered.text
    assert [item["id"] for item in filtered.json()] == [body["id"]]

    no_matches = await client.get("api/v1/connections?provider=slack", headers=logged_in_headers)
    assert no_matches.status_code == 200, no_matches.text
    assert no_matches.json() == []

    resolver = get_connection_resolver_service()
    ref = ConnectionRef(provider="google_workspace", name="work")
    interactive = ExecutionPrincipal(
        kind="actor",
        user_id=body["owner_id"],
        actor_id=body["owner_id"],
        interactive=True,
    )
    resolved = await resolver.resolve(ConnectionResolutionRequest(ref=ref, principal=interactive))
    assert resolved.access_token.get_secret_value() == "access-token-do-not-return"
    assert resolved.granted_scopes == frozenset({"calendar.readonly"})

    with pytest.raises(ScopeMissingError):
        await resolver.resolve(
            ConnectionResolutionRequest(
                ref=ref,
                principal=interactive,
                required_scopes=frozenset({"calendar.write"}),
            )
        )

    non_interactive = ExecutionPrincipal(
        kind="flow_owner",
        user_id=body["owner_id"],
        actor_id=body["owner_id"],
        interactive=False,
    )
    with pytest.raises(ConnectionNotAuthorizedError):
        await resolver.resolve(ConnectionResolutionRequest(ref=ref, principal=non_interactive))

    unattended_created = await client.post(
        "api/v1/connections",
        json=_payload(name="automation", allow_non_interactive=True),
        headers=logged_in_headers,
    )
    assert unattended_created.status_code == 201, unattended_created.text
    unattended = await resolver.resolve(
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="google_workspace", name="automation"),
            principal=non_interactive,
        )
    )
    assert unattended.access_token.get_secret_value() == "access-token-do-not-return"

    tested = await client.post(
        f"api/v1/connections/{body['id']}/test",
        json={"required_scopes": ["calendar.readonly"]},
        headers=logged_in_headers,
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["health"] == "healthy"
    _assert_no_credentials(tested.json())

    async with session_scope() as session:
        stored = (
            await session.exec(select(ConnectionSecret).where(ConnectionSecret.connection_id == UUID(body["id"])))
        ).one()
        assert "access-token-do-not-return" not in stored.encrypted_payload
        assert "refresh-token-do-not-return" not in stored.encrypted_payload

    revoked = await client.post(f"api/v1/connections/{body['id']}/revoke", headers=logged_in_headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["has_credentials"] is False
    _assert_no_credentials(revoked.json())

    deleted = await client.delete(f"api/v1/connections/{body['id']}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text


@pytest.mark.usefixtures("active_user")
async def test_non_owner_cannot_test_or_delete_connection(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    connection_id = created.json()["id"]

    username = f"other-{uuid4().hex}"
    password = "test-non-owner-password"  # noqa: S105  # pragma: allowlist secret
    async with session_scope() as session:
        other = User(
            username=username,
            password=get_auth_service().get_password_hash(password),
            is_active=True,
        )
        session.add(other)
        await session.flush()
        await session.refresh(other)
        other_id = other.id

    login = await client.post("api/v1/login", data={"username": username, "password": password})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    tested = await client.post(
        f"api/v1/connections/{connection_id}/test",
        json={"required_scopes": []},
        headers=headers,
    )
    deleted = await client.delete(f"api/v1/connections/{connection_id}", headers=headers)
    assert tested.status_code == 404
    assert deleted.status_code == 404

    async with session_scope() as session:
        other = await session.get(User, other_id)
        if other is not None:
            await session.delete(other)


@pytest.mark.usefixtures("active_super_user")
async def test_superuser_can_create_and_list_instance_connection(
    client: AsyncClient,
    logged_in_headers_super_user: dict[str, str],
) -> None:
    created = await client.post(
        "api/v1/connections",
        json=_payload(ownership_mode="instance"),
        headers=logged_in_headers_super_user,
    )
    assert created.status_code == 201, created.text
    assert created.json()["owner_id"] is None
    assert created.json()["ownership_mode"] == "instance"

    listed = await client.get("api/v1/connections", headers=logged_in_headers_super_user)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
