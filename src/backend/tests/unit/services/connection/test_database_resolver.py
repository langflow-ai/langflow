"""Resolver-contract coverage for the database-backed connection resolver."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.connection import DatabaseConnectionResolverService
from langflow.services.connection import service as connection_service
from langflow.services.database.models.connection import Connection, ConnectionCreate
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import ConnectionNotAuthorizedError, ConnectionUnresolvedError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal, ResourceVisibilityScope
from lfx.services.deps import get_connection_resolver
from sqlalchemy import event

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


class _ShareAuthz:
    """Authorization plugin stand-in that supports cross-user fetch."""

    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.visibility: ResourceVisibilityScope | None = None
        self.batch_calls: list[list[tuple[str, str]]] = []

    async def supports_cross_user_fetch(self) -> bool:
        return True

    async def get_resource_visibility(self, **_: object) -> ResourceVisibilityScope | None:
        return self.visibility

    async def batch_enforce(self, *, user_id, domain, requests, context=None) -> list[bool]:  # noqa: ARG002
        self.batch_calls.append(list(requests))
        return [self.allow] * len(requests)


def _connection_payload(name: str) -> ConnectionCreate:
    return ConnectionCreate.model_validate(
        {
            "provider_key": "google_workspace",
            "name": name,
            "display_name": "Foreign Google",
            "ownership_mode": "user",
            "granted_scopes": ["calendar.readonly"],
            "executing_identity": {"identity": "user_delegated", "account": {"id": "account-2"}},
            "credentials": {"access_token": "foreign-access-token"},  # pragma: allowlist secret
        }
    )


async def _seed_foreign_connections(count: int, *, name: str) -> list[str]:
    """Create ``count`` users that each own a connection with the same handle."""
    service = get_connection_resolver_service()
    ids: list[str] = []
    async with session_scope() as session:
        for _ in range(count):
            owner = User(username=f"foreign-{uuid4().hex}", password="unused-hash", is_active=True)  # noqa: S106
            session.add(owner)
            await session.flush()
            created = await service.create(session, user=owner, payload=_connection_payload(name))
            ids.append(str(created.id))
    return ids


@contextmanager
def _loaded_connection_ids() -> Iterator[list[str]]:
    """Record every connection row the ORM materializes inside the block."""
    loaded: list[str] = []

    def _on_load(target: Connection, _context: object) -> None:
        loaded.append(str(target.id))

    event.listen(Connection, "load", _on_load)
    try:
        yield loaded
    finally:
        event.remove(Connection, "load", _on_load)


async def _create_connection(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str,
    allow_non_interactive: bool = False,
) -> dict:
    response = await client.post(
        "api/v1/connections",
        json={
            "provider_key": "google_workspace",
            "name": name,
            "display_name": "Shared Google",
            "ownership_mode": "user",
            "granted_scopes": ["calendar.readonly"],
            "executing_identity": {"identity": "user_delegated", "account": {"id": "account-1"}},
            "allow_non_interactive": allow_non_interactive,
            "credentials": {"access_token": "shared-access-token", "token_type": "Bearer"},  # pragma: allowlist secret
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def share_authz(monkeypatch: pytest.MonkeyPatch) -> _ShareAuthz:
    authz = _ShareAuthz()
    monkeypatch.setattr(connection_service, "get_authorization_service", lambda: authz)
    monkeypatch.setattr(
        connection_service,
        "get_settings_service",
        lambda: SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True)),
    )
    return authz


@pytest.mark.usefixtures("client")
async def test_component_lookup_returns_the_database_resolver() -> None:
    # Components resolve through lfx's lookup, which rejects resolvers that are not ready.
    resolver = get_connection_resolver()

    assert isinstance(resolver, DatabaseConnectionResolverService)
    assert resolver is get_connection_resolver_service()


@pytest.mark.usefixtures("active_user")
async def test_explicit_share_resolves_for_actor_on_share_family(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    share_authz: _ShareAuthz,
) -> None:
    created = await _create_connection(client, logged_in_headers, name="shared_chat")
    other_user = str(uuid4())
    principal = ExecutionPrincipal(
        kind="actor", user_id=other_user, actor_id=other_user, family="interactive_chat", interactive=True
    )

    resolved = await get_connection_resolver_service().resolve(
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="google_workspace", name="shared_chat"), principal=principal
        )
    )

    assert resolved.access_token.get_secret_value() == "shared-access-token"
    assert resolved.connection_id == created["id"]
    assert share_authz.batch_calls == [[(f"connection:{created['id']}", "execute")]]


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(
    ("kind", "family", "interactive"),
    [
        ("actor", "legacy_mcp", True),
        ("actor", "mcp_projects", True),
        ("actor", None, True),
        ("flow_owner", "webhook", False),
        ("deployment_owner", "deployments", False),
    ],
)
async def test_explicit_share_never_resolves_outside_share_families(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    share_authz: _ShareAuthz,
    kind: str,
    family: str | None,
    interactive: bool,  # noqa: FBT001
) -> None:
    name = f"owner_only_{uuid4().hex[:8]}"
    await _create_connection(client, logged_in_headers, name=name, allow_non_interactive=True)
    other_user = str(uuid4())
    principal = ExecutionPrincipal(
        kind=kind, user_id=other_user, actor_id=other_user, family=family, interactive=interactive
    )

    with pytest.raises(ConnectionUnresolvedError):
        await get_connection_resolver_service().resolve(
            ConnectionResolutionRequest(ref=ConnectionRef(provider="google_workspace", name=name), principal=principal)
        )
    assert share_authz.batch_calls == []


@pytest.mark.usefixtures("active_user")
async def test_denied_share_is_unresolved(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    share_authz: _ShareAuthz,
) -> None:
    share_authz.allow = False
    await _create_connection(client, logged_in_headers, name="denied_share")
    other_user = str(uuid4())
    principal = ExecutionPrincipal(kind="actor", user_id=other_user, family="v1_run", interactive=True)

    with pytest.raises(ConnectionUnresolvedError):
        await get_connection_resolver_service().resolve(
            ConnectionResolutionRequest(
                ref=ConnectionRef(provider="google_workspace", name="denied_share"), principal=principal
            )
        )


@pytest.mark.usefixtures("active_user")
async def test_resolve_fails_closed_when_policy_changes_after_authorization(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await _create_connection(client, logged_in_headers, name="drift")
    resolver = get_connection_resolver_service()
    owner = ExecutionPrincipal(kind="actor", user_id=created["owner_id"], interactive=True)
    request = ConnectionResolutionRequest(ref=ConnectionRef(provider="google_workspace", name="drift"), principal=owner)
    policy = await resolver._get_access_policy(request)

    async with session_scope() as session:
        row = await session.get(Connection, UUID(created["id"]))
        row.allow_non_interactive = True
        session.add(row)
    with pytest.raises(ConnectionNotAuthorizedError):
        await resolver._resolve(request, policy)

    async with session_scope() as session:
        await session.delete(await session.get(Connection, UUID(created["id"])))
    with pytest.raises(ConnectionUnresolvedError):
        await resolver._resolve(request, policy)


@pytest.mark.usefixtures("active_user")
async def test_owned_resolution_never_loads_foreign_rows_with_the_same_handle(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    share_authz: _ShareAuthz,
) -> None:
    await _seed_foreign_connections(25, name="work")
    created = await _create_connection(client, logged_in_headers, name="work")
    owner = ExecutionPrincipal(kind="actor", user_id=created["owner_id"], family="interactive_chat", interactive=True)

    with _loaded_connection_ids() as loaded:
        resolved = await get_connection_resolver_service().resolve(
            ConnectionResolutionRequest(ref=ConnectionRef(provider="google_workspace", name="work"), principal=owner)
        )

    assert resolved.connection_id == created["id"]
    assert set(loaded) == {created["id"]}
    assert share_authz.batch_calls == []


@pytest.mark.usefixtures("active_user")
async def test_share_lookup_authorizes_only_rows_in_the_visibility_scope(share_authz: _ShareAuthz) -> None:
    foreign_ids = await _seed_foreign_connections(25, name="team")
    target = foreign_ids[7]
    share_authz.visibility = ResourceVisibilityScope(resource_ids=(UUID(target),))
    actor = str(uuid4())
    principal = ExecutionPrincipal(kind="actor", user_id=actor, family="v1_run", interactive=True)

    with _loaded_connection_ids() as loaded:
        resolved = await get_connection_resolver_service().resolve(
            ConnectionResolutionRequest(
                ref=ConnectionRef(provider="google_workspace", name="team"), principal=principal
            )
        )

    assert resolved.connection_id == target
    assert set(loaded) == {target}
    assert share_authz.batch_calls == [[(f"connection:{target}", "execute")]]


@pytest.mark.usefixtures("active_user")
async def test_share_lookup_fails_closed_past_the_candidate_cap(
    monkeypatch: pytest.MonkeyPatch,
    share_authz: _ShareAuthz,
) -> None:
    monkeypatch.setattr(connection_service, "_MAX_SHARE_CANDIDATES", 3)
    await _seed_foreign_connections(4, name="crowded")
    actor = str(uuid4())
    principal = ExecutionPrincipal(kind="actor", user_id=actor, family="v1_run", interactive=True)

    with _loaded_connection_ids() as loaded, pytest.raises(ConnectionUnresolvedError):
        await get_connection_resolver_service().resolve(
            ConnectionResolutionRequest(
                ref=ConnectionRef(provider="google_workspace", name="crowded"), principal=principal
            )
        )

    assert len(loaded) == 4  # the cap plus the one row that proves it was exceeded
    assert share_authz.batch_calls == []
