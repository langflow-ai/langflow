"""API coverage for connection ownership and secret-safe serialization."""

from __future__ import annotations

import contextlib
import json
import re
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from langflow.services.auth.utils import encrypt_api_key, get_auth_service
from langflow.services.database.models.connection import ConnectionSecret
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_connection_resolver_service, get_db_service, session_scope
from lfx.integrations.errors import ConnectionNotAuthorizedError, ConnectionUnresolvedError, ScopeMissingError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.deps import get_settings_service
from sqlalchemy import event
from sqlmodel import select

from tests.unit.services.authorization._policy_double import install_policy_authz

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

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


@contextlib.contextmanager
def _connection_row_updates() -> Iterator[list[str]]:
    """Record UPDATEs against the connection table, which is how its row lock is taken."""
    engine = get_db_service().engine
    sync_engine = getattr(engine, "sync_engine", engine)
    statements: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        if re.match(r"\s*UPDATE\s+connection\b", statement, re.IGNORECASE):
            statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(sync_engine, "before_cursor_execute", record)


@contextlib.asynccontextmanager
async def _other_user_headers(client: AsyncClient) -> AsyncIterator[dict[str, str]]:
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
    try:
        yield {"Authorization": f"Bearer {login.json()['access_token']}"}
    finally:
        async with session_scope() as session:
            other = await session.get(User, other_id)
            if other is not None:
                await session.delete(other)


async def _login_new_user(client: AsyncClient, *, is_superuser: bool = False) -> dict[str, str]:
    """Create a second account; the shared fixtures all reuse one username."""
    username = f"user-{uuid4().hex}"
    password = "test-connection-password"  # noqa: S105  # pragma: allowlist secret
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_auth_service().get_password_hash(password),
            is_active=True,
            is_superuser=is_superuser,
        )
        session.add(user)
    login = await client.post("api/v1/login", data={"username": username, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _replace_envelope(connection_id: str, encrypted_payload: str | None) -> None:
    """Overwrite or remove a stored envelope, as a key change or data loss would."""
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(connection_id))
        assert secret is not None
        if encrypted_payload is None:
            await session.delete(secret)
        else:
            secret.encrypted_payload = encrypted_payload
            session.add(secret)


def _envelope(**fields: object) -> str:
    return json.dumps({"version": 1, "access_token": "restored-access-token", **fields})


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

    async with _other_user_headers(client) as headers:
        # A caller who cannot see the connection must not take its row lock:
        # otherwise a known UUID lets them stall the owner's refresh or revoke.
        with _connection_row_updates() as updates:
            tested = await client.post(
                f"api/v1/connections/{connection_id}/test",
                json={"required_scopes": []},
                headers=headers,
            )
            revoked = await client.post(f"api/v1/connections/{connection_id}/revoke", headers=headers)
            deleted = await client.delete(f"api/v1/connections/{connection_id}", headers=headers)
            started = await client.post(
                f"api/v1/connections/{connection_id}/oauth/start",
                json={"registration_id": "unknown", "scopes": ["read"]},
                headers=headers,
            )
    assert started.status_code == 404
    assert tested.status_code == 404
    assert revoked.status_code == 404
    assert deleted.status_code == 404
    assert updates == []

    # The owner still locks the row, which also shows the listener sees the lock.
    with _connection_row_updates() as updates:
        health = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert health.status_code == 200, health.text
    assert updates


@pytest.mark.usefixtures("active_user")
async def test_denied_cross_user_fetch_does_not_lock_connection(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """A plugin loads rows across users, so its deny must also come before the lock."""
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    connection_id = created.json()["id"]

    async with _other_user_headers(client) as headers:
        with install_policy_authz(get_settings_service()), _connection_row_updates() as updates:
            revoked = await client.post(f"api/v1/connections/{connection_id}/revoke", headers=headers)
            health = await client.post(f"api/v1/connections/{connection_id}/health", headers=headers)
    assert revoked.status_code == 403, revoked.text
    assert health.status_code == 403, health.text
    assert updates == []

    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(connection_id))
        assert secret is not None


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


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(
    "unreadable_envelope",
    [
        # Written under a different secret key: what a restart with a rotated key leaves behind.
        pytest.param(lambda: Fernet(Fernet.generate_key()).encrypt(_envelope().encode()).decode(), id="foreign-key"),
        pytest.param(lambda: encrypt_api_key(_envelope(expires_at="not-a-date")), id="corrupt-envelope"),
    ],
)
async def test_unreadable_credential_is_an_error_not_a_missing_connection(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    unreadable_envelope,
) -> None:
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["status"], body["status_reason"]) == ("ready", None)
    resolver = get_connection_resolver_service()
    ref = ConnectionRef(provider="google_workspace", name="work")
    owner = ExecutionPrincipal(kind="actor", user_id=body["owner_id"], actor_id=body["owner_id"], interactive=True)

    await _replace_envelope(body["id"], unreadable_envelope())
    checked = await client.post(f"api/v1/connections/{body['id']}/health", headers=logged_in_headers)
    assert checked.status_code == 200, checked.text
    assert {key: checked.json()[key] for key in ("status", "status_reason", "health", "has_credentials")} == {
        "status": "error",
        "status_reason": "credential-undecryptable",
        "health": "unhealthy",
        "has_credentials": True,
    }
    listed = (await client.get("api/v1/connections", headers=logged_in_headers)).json()
    assert [(item["status"], item["status_reason"]) for item in listed] == [("error", "credential-undecryptable")]

    with pytest.raises(ConnectionUnresolvedError) as undecryptable:
        await resolver.resolve(ConnectionResolutionRequest(ref=ref, principal=owner))
    assert undecryptable.value.details == {"reason": "credential-undecryptable"}
    assert "could not be decrypted" in str(undecryptable.value)
    assert "Configure the connection" not in str(undecryptable.value)
    # Neither the decryption failure nor decrypted plaintext is reachable from the public error.
    assert undecryptable.value.__cause__ is None
    assert undecryptable.value.__context__ is None
    assert (await resolver.describe(ref, owner)).status == "unavailable"

    # Control: a lost envelope is a different cause, and says so.
    await _replace_envelope(body["id"], None)
    lost = (await client.post(f"api/v1/connections/{body['id']}/health", headers=logged_in_headers)).json()
    assert (lost["status"], lost["status_reason"], lost["has_credentials"]) == ("error", "credential-missing", False)
    with pytest.raises(ConnectionUnresolvedError) as missing:
        await resolver.resolve(ConnectionResolutionRequest(ref=ref, principal=owner))
    assert missing.value.details == {"reason": "missing"}
    assert (await resolver.describe(ref, owner)).status == "missing"

    # A readable envelope and a passing check clear the error and its reason.
    async with session_scope() as session:
        session.add(ConnectionSecret(connection_id=UUID(body["id"]), encrypted_payload=encrypt_api_key(_envelope())))
    restored = (await client.post(f"api/v1/connections/{body['id']}/health", headers=logged_in_headers)).json()
    assert (restored["status"], restored["status_reason"], restored["health"]) == ("ready", None, "healthy")


@pytest.mark.usefixtures("active_user")
async def test_owner_changes_non_interactive_use_without_reauthorizing(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post(
        "api/v1/connections", json=_payload(allow_non_interactive=True), headers=logged_in_headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    resolver = get_connection_resolver_service()
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="google_workspace", name="work"),
        principal=ExecutionPrincipal(
            kind="flow_owner", user_id=body["owner_id"], actor_id=body["owner_id"], interactive=False
        ),
    )
    assert (await resolver.resolve(request)).access_token.get_secret_value() == "access-token-do-not-return"

    withdrawn = await client.patch(
        f"api/v1/connections/{body['id']}", json={"allow_non_interactive": False}, headers=logged_in_headers
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["allow_non_interactive"] is False
    # Same handle, same credential: nothing to re-authorize.
    assert {key: withdrawn.json()[key] for key in ("id", "name", "status", "has_credentials")} == {
        "id": body["id"],
        "name": "work",
        "status": "ready",
        "has_credentials": True,
    }
    _assert_no_credentials(withdrawn.json())
    with pytest.raises(ConnectionNotAuthorizedError):
        await resolver.resolve(request)

    restored = await client.patch(
        f"api/v1/connections/{body['id']}",
        json={"allow_non_interactive": True, "display_name": "  Automation Google  "},
        headers=logged_in_headers,
    )
    assert restored.status_code == 200, restored.text
    assert (restored.json()["allow_non_interactive"], restored.json()["display_name"]) == (True, "Automation Google")
    assert (await resolver.resolve(request)).access_token.get_secret_value() == "access-token-do-not-return"

    for invalid in (
        {},
        {"allow_non_interactive": None},
        {"display_name": "   "},
        {"name": "renamed"},
        {"granted_scopes": ["calendar.write"]},
        {"credentials": {"access_token": "replacement"}},  # pragma: allowlist secret
    ):
        rejected = await client.patch(f"api/v1/connections/{body['id']}", json=invalid, headers=logged_in_headers)
        assert rejected.status_code == 422, (invalid, rejected.text)


@pytest.mark.usefixtures("active_user")
async def test_only_the_owner_may_enable_non_interactive_use(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post(
        "api/v1/connections", json=_payload(allow_non_interactive=True), headers=logged_in_headers
    )
    assert created.status_code == 201, created.text
    connection_url = f"api/v1/connections/{created.json()['id']}"
    admin_headers = await _login_new_user(client, is_superuser=True)

    # Narrowing someone else's exposure is allowed; widening it is not.
    narrowed = await client.patch(connection_url, json={"allow_non_interactive": False}, headers=admin_headers)
    assert narrowed.status_code == 200, narrowed.text
    widened = await client.patch(connection_url, json={"allow_non_interactive": True}, headers=admin_headers)
    assert widened.status_code == 403, widened.text

    by_owner = await client.patch(connection_url, json={"allow_non_interactive": True}, headers=logged_in_headers)
    assert by_owner.status_code == 200, by_owner.text
    assert by_owner.json()["allow_non_interactive"] is True


@pytest.mark.usefixtures("active_super_user")
async def test_instance_connections_are_changed_only_by_superusers(
    client: AsyncClient,
    logged_in_headers_super_user: dict[str, str],
) -> None:
    created = await client.post(
        "api/v1/connections", json=_payload(ownership_mode="instance"), headers=logged_in_headers_super_user
    )
    assert created.status_code == 201, created.text
    connection_url = f"api/v1/connections/{created.json()['id']}"
    member_headers = await _login_new_user(client)

    # Every user can see and use the instance connection...
    listed = await client.get("api/v1/connections", headers=member_headers)
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
    checked = await client.post(f"{connection_url}/health", headers=member_headers)
    assert checked.status_code == 200, checked.text

    # ...but cannot change, re-authorize, or remove it, even with authorization
    # disabled, and is refused before the row lock is taken.
    with _connection_row_updates() as locks:
        denied = [
            await client.patch(connection_url, json={"display_name": "Mine now"}, headers=member_headers),
            await client.patch(connection_url, json={"allow_non_interactive": True}, headers=member_headers),
            await client.post(
                f"{connection_url}/oauth/start",
                json={"registration_id": "google", "scopes": ["calendar.readonly"]},
                headers=member_headers,
            ),
            await client.post(f"{connection_url}/revoke", headers=member_headers),
            await client.delete(connection_url, headers=member_headers),
        ]
    assert [response.status_code for response in denied] == [403, 403, 403, 403, 403]
    assert locks == []
    unchanged = (await client.get("api/v1/connections", headers=member_headers)).json()[0]
    assert (unchanged["display_name"], unchanged["allow_non_interactive"], unchanged["status"]) == (
        "Work Google",
        False,
        "ready",
    )

    renamed = await client.patch(
        connection_url,
        json={"display_name": "Shared Google", "allow_non_interactive": True},
        headers=logged_in_headers_super_user,
    )
    assert renamed.status_code == 200, renamed.text
    deleted = await client.delete(connection_url, headers=logged_in_headers_super_user)
    assert deleted.status_code == 204, deleted.text
