"""The resolved credential carries the connection's executing identity.

Slack user and bot tokens share scope names (``chat:write`` is both a User
Token Scope and a Bot Token Scope), so ``granted_scopes`` cannot tell them
apart. Bundle capabilities that must run as one identity compare
``ResolvedCredential.identity`` instead, which is only trustworthy if the
database-backed resolver actually copies it off the connection row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langflow.services.deps import get_connection_resolver_service
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


def _slack_payload(*, name: str, identity: str) -> dict:
    return {
        "provider_key": "slack",
        "name": name,
        "display_name": f"Slack {identity}",
        "ownership_mode": "user",
        "granted_scopes": ["chat:write"],
        "executing_identity": {
            "identity": identity,
            "account": {"id": f"{identity}-account", "display": "Acme", "tenant_id": "T0123456789"},
        },
        "credentials": {
            "access_token": f"{identity}-access-token-do-not-return",
            "token_type": "Bearer",
        },
    }


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(("name", "identity"), [("workspace_bot", "bot"), ("workspace_user", "user_delegated")])
async def test_resolved_credential_reports_the_row_identity(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    name: str,
    identity: str,
) -> None:
    created = await client.post(
        "api/v1/connections",
        json=_slack_payload(name=name, identity=identity),
        headers=logged_in_headers,
    )
    assert created.status_code == 201, created.text
    owner_id = created.json()["owner_id"]

    resolver = get_connection_resolver_service()
    principal = ExecutionPrincipal(kind="actor", user_id=owner_id, actor_id=owner_id, interactive=True)
    resolved = await resolver.resolve(
        ConnectionResolutionRequest(ref=ConnectionRef(provider="slack", name=name), principal=principal)
    )

    assert resolved.identity == identity
    assert resolved.granted_scopes == frozenset({"chat:write"})
    assert f"{identity}-access-token-do-not-return" not in repr(resolved)
