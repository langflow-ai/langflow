"""GitLab token checks reject unverified claims and persist provider rejections."""

import json
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from hashlib import sha256
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.connection.service import _encrypt_credential_payload
from langflow.services.database.models.connection import Connection, ConnectionSecret
from langflow.services.deps import get_connection_resolver_service, session_scope
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.gitlab import runtime
from lfx.integrations.errors import AuthExpiredError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_gitlab.client import GitLabClient, api_origin

from tests.unit.services.triggers.test_gitlab_lifecycle import (
    gitlab,  # noqa: F401 - register the installed provider fixture
)

pytestmark = pytest.mark.no_blockbuster

TOKEN = "synthetic-gitlab-token"  # noqa: S105 - synthetic provider fixture


def body():
    return {
        "provider_key": "gitlab",
        "name": "validation",
        "display_name": "GitLab validation",
        "executing_identity": {
            "identity": "user_delegated",
            "account": {"id": "1", "display": "forged-admin", "tenant_id": "https://gitlab.com"},
        },
        "granted_scopes": ["api"],
        "credentials": {"access_token": TOKEN},
    }


async def legacy_connection(user_id):
    async with session_scope() as session:
        row = Connection(
            owner_id=user_id,
            ownership_mode="user",
            provider_key="gitlab",
            name="validation",
            display_name="GitLab validation",
            status="ready",
            health="healthy",
            granted_scopes=["api"],
            executing_identity=body()["executing_identity"],
            allow_non_interactive=True,
        )
        session.add(row)
        await session.flush()
        session.add(
            ConnectionSecret(
                connection_id=row.id,
                encrypted_payload=_encrypt_credential_payload(json.dumps({"version": 1, "access_token": TOKEN})),
            )
        )
        return row.id


@pytest.mark.parametrize(
    "origin",
    [
        "http://gitlab.com",
        "https://gitlab.com/api/v4",
        "https://10.0.0.5",
        "https://gitlab.com:8443",
        "https://user:pw@gitlab.com",  # pragma: allowlist secret
        "https://gitlab.local",
    ],
)
async def test_unavailable_provider_refuses_connection_creation(
    gitlab,  # noqa: F811
    client,
    logged_in_headers,
    monkeypatch,
    origin,
):
    monkeypatch.setenv("LANGFLOW_GITLAB_ORIGIN", origin)
    original_entries = registry.metadata.entry_points
    entry = next(iter(original_entries(group=registry.ENTRY_POINT_GROUP).select(name="gitlab")))

    def configured_provider():
        return replace(runtime.PROVIDER, api_origins=(api_origin(),))

    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [SimpleNamespace(name="gitlab", dist=entry.dist, load=configured_provider)]
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original_entries(**kwargs),
    )
    monkeypatch.setattr(registry, "_cache_key", None)
    response = await client.post("api/v1/connections", json=body(), headers=logged_in_headers)
    assert response.status_code == 422, response.text
    assert TOKEN not in response.text
    assert not gitlab.requests
    rows = await client.get("api/v1/connections?provider=gitlab", headers=logged_in_headers)
    assert rows.json() == []


@pytest.mark.parametrize("endpoint", ["health", "test"])
@pytest.mark.usefixtures("gitlab")
async def test_health_check_contacts_gitlab_and_rejects_revoked_token(
    client, logged_in_headers, active_user, monkeypatch, endpoint
):
    connection_id = await legacy_connection(active_user.id)
    requests = []

    def rejected(request):
        requests.append(request)
        return httpx.Response(401, text=TOKEN)

    monkeypatch.setattr(
        "langflow.services.triggers.providers.gitlab.credentials.GitLabClient",
        partial(GitLabClient, transport=httpx.MockTransport(rejected)),
    )
    response = await client.post(f"api/v1/connections/{connection_id}/{endpoint}", json={}, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "expired"
    assert response.json()["health"] == "unhealthy"
    assert response.json()["health_checked_at"] is not None
    assert TOKEN not in response.text
    assert len(requests) == 1


async def test_health_check_replaces_unverified_account_claims(
    gitlab,  # noqa: F811
    client,
    logged_in_headers,
    active_user,
):
    connection_id = await legacy_connection(active_user.id)
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, connection_id)
        secret.updated_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        session.add(secret)
    async with session_scope() as session:
        secret_before = await session.get(ConnectionSecret, connection_id)
        token_updated_at = secret_before.updated_at
    response = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["health"] == "healthy"
    assert response.json()["executing_identity"]["account"]["id"] == "9"
    assert response.json()["executing_identity"]["account"]["display"] == "owner"
    assert len(gitlab.requests) == 2
    resolved = await get_connection_resolver_service().resolve(
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="gitlab", name="validation"),
            principal=ExecutionPrincipal(kind="actor", user_id=str(active_user.id), interactive=True),
        )
    )
    assert resolved.expires_at is not None
    async with session_scope() as session:
        secret_after = await session.get(ConnectionSecret, connection_id)
        assert secret_after.updated_at == token_updated_at


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.usefixtures("gitlab")
async def test_unavailable_gitlab_health_probe_does_not_expire_connection(
    client, logged_in_headers, active_user, monkeypatch, status
):
    connection_id = await legacy_connection(active_user.id)
    monkeypatch.setattr(
        "langflow.services.triggers.providers.gitlab.credentials.GitLabClient",
        partial(GitLabClient, transport=httpx.MockTransport(lambda _request: httpx.Response(status, text=TOKEN))),
    )
    response = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["health"] == "unhealthy"
    assert response.json()["status"] == "ready"
    assert TOKEN not in response.text


@pytest.mark.parametrize("stale", [False, True])
@pytest.mark.usefixtures("gitlab")
async def test_runtime_token_rejection_expires_only_the_rejected_credential(active_user, stale):
    connection_id = await legacy_connection(active_user.id)
    lease = CredentialLease(
        get_connection_resolver_service(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="gitlab", name="validation"),
            principal=ExecutionPrincipal(kind="actor", user_id=str(active_user.id), interactive=True),
        ),
    )
    assert await lease.get_token() == TOKEN
    if stale:
        resolved = await get_connection_resolver_service().resolve(
            replace(lease._request, rejected_token_digest=sha256(b"older-token").hexdigest())
        )
        assert resolved.access_token.get_secret_value() == TOKEN
    else:
        with pytest.raises(AuthExpiredError):
            await lease.get_token_after_auth_error(AuthExpiredError(provider="gitlab"), rejected_token=TOKEN)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        assert row.status == ("ready" if stale else "expired")
        assert row.health == ("healthy" if stale else "unhealthy")
