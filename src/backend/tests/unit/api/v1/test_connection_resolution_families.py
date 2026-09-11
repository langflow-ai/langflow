"""INT-6: one allow-or-deny connection test per execution-principal family.

These exercise the real ``DatabaseConnectionResolverService`` against real
``Connection``/``ConnectionSecret`` rows, using the same
``execution_principal_for`` helper the routes stamp with. Testing the helper plus
the resolver (rather than 13 HTTP round trips) keeps one assertion per family
readable while still covering the code that actually decides.

The matrix in ``scripts/ci/execution_principal_matrix.json`` is the contract; the
table-driven test below reads it so a new family cannot be added without an
allow/deny expectation.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.execution_errors import (
    SAFE_INTEGRATION_ERROR_MESSAGE,
    error_details_for_client,
)
from langflow.api.utils.execution_principal import (
    FAMILY_A2A,
    FAMILY_INTERACTIVE_CHAT,
    FAMILY_LEGACY_MCP,
    FAMILY_LEGACY_PUBLIC_CHAT,
    FAMILY_MCP_PROJECTS,
    FAMILY_WEBHOOK,
    FAMILY_WORKFLOW_HITL_V2,
    FAMILY_WORKFLOW_PUBLIC_V2,
    execution_principal_for,
)
from langflow.services.authorization.public_access import public_execution_user
from langflow.services.connection import service as connection_service
from langflow.services.deps import get_connection_resolver_service
from lfx.integrations.errors import (
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    IntegrationError,
)
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

PROVIDER = "google_workspace"
ACCESS_TOKEN = "access-token-do-not-return"  # noqa: S105  # pragma: allowlist secret

MATRIX_PATH = Path(__file__).resolve().parents[6] / "scripts" / "ci" / "execution_principal_matrix.json"

# The two rows every family is measured against: a plain owned connection, and the
# same connection with the per-connection non-interactive opt-in set.
_RESOLVES_PLAIN_OWNED_ROW = {"owner_or_explicit_share", "owner_only"}
_RESOLVES_OPTED_IN_ROW = {
    "owner_or_explicit_share",
    "owner_only",
    "owner_non_interactive_opt_in",
    "job_owner_reresolved",
}


def _payload(*, name: str, ownership_mode: str = "user", allow_non_interactive: bool = False) -> dict:
    return {
        "provider_key": PROVIDER,
        "name": name,
        "display_name": "Work Google",
        "ownership_mode": ownership_mode,
        "granted_scopes": ["calendar.readonly"],
        "executing_identity": {
            "identity": "user_delegated",
            "account": {"id": "account-123", "display": "Work", "tenant_id": "tenant-123"},
        },
        "allow_non_interactive": allow_non_interactive,
        "credentials": {"access_token": ACCESS_TOKEN, "token_type": "Bearer"},
    }


def _matrix_entrypoints() -> list[dict]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["entrypoints"]


async def _create_connection(client: AsyncClient, headers: dict[str, str], **kwargs) -> dict:
    created = await client.post("api/v1/connections", json=_payload(**kwargs), headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


async def _resolve(name: str, principal) -> object:
    resolver = get_connection_resolver_service()
    return await resolver.resolve(
        ConnectionResolutionRequest(ref=ConnectionRef(provider=PROVIDER, name=name), principal=principal)
    )


@pytest.mark.usefixtures("active_user")
async def test_connection_resolution_matches_the_matrix_for_every_family(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """Every matrix family gets an allow-or-deny assertion against a real row.

    ``owner_id`` is passed as both the actor and the resource owner, so this is
    the most permissive shape each family can be in: whatever is denied here is
    denied by the rule itself, not by an identity mismatch.
    """
    plain = await _create_connection(client, logged_in_headers, name=f"plain_{uuid4().hex[:8]}")
    opted_in = await _create_connection(
        client, logged_in_headers, name=f"unattended_{uuid4().hex[:8]}", allow_non_interactive=True
    )
    owner_id = plain["owner_id"]
    owner = SimpleNamespace(id=UUID(owner_id))

    entrypoints = _matrix_entrypoints()
    assert entrypoints, "the execution-principal matrix must not be empty"

    for entrypoint in entrypoints:
        family = entrypoint["family"]
        rule = entrypoint["connection_resolution"]
        principal = execution_principal_for(family, user=owner, flow_owner_id=owner_id)
        assert principal.family == family

        for row, expected in (
            (plain, rule in _RESOLVES_PLAIN_OWNED_ROW),
            (opted_in, rule in _RESOLVES_OPTED_IN_ROW),
        ):
            if expected:
                resolved = await _resolve(row["name"], principal)
                assert resolved.access_token.get_secret_value() == ACCESS_TOKEN, (
                    f"{family} ({rule}) should have resolved {row['name']}"
                )
            else:
                with pytest.raises(IntegrationError):
                    await _resolve(row["name"], principal)


@pytest.mark.usefixtures("active_user")
async def test_public_flow_referencing_a_user_connection_fails_closed_and_is_sanitized(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """A public flow that names an owner's connection gets nothing and says nothing.

    Both public families are checked: the v1 shareable playground
    (``legacy_public_chat``) and the v2 public stream (``workflow_public_v2``).
    """
    row = await _create_connection(
        client, logged_in_headers, name=f"public_{uuid4().hex[:8]}", allow_non_interactive=True
    )
    public_user = public_execution_user()

    for family in (FAMILY_LEGACY_PUBLIC_CHAT, FAMILY_WORKFLOW_PUBLIC_V2):
        principal = execution_principal_for(family, user=public_user, flow_owner_id=row["owner_id"])
        assert principal.kind == "anonymous_public"
        assert principal.user_id is None
        assert principal.interactive is False

        with pytest.raises(IntegrationError) as raised:
            await _resolve(row["name"], principal)

        # The public error policy: a typed code the UI can act on, and nothing else.
        details = error_details_for_client(raised.value, expose_details=False)
        assert details.code in {"connection-unresolved", "connection-not-authorized"}
        assert details.message == SAFE_INTEGRATION_ERROR_MESSAGE
        assert details.stack_trace == ""
        assert details.details == {}
        body = json.dumps(details.as_client_body())
        assert ACCESS_TOKEN not in body
        assert row["owner_id"] not in body
        assert row["name"] not in body


@pytest.mark.usefixtures("active_user")
async def test_webhook_connection_without_non_interactive_opt_in_fails_closed(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """A webhook run is unattended, so the owner must have opted the connection in."""
    row = await _create_connection(client, logged_in_headers, name=f"webhook_{uuid4().hex[:8]}")
    principal = execution_principal_for(
        FAMILY_WEBHOOK, user=SimpleNamespace(id=UUID(row["owner_id"])), flow_owner_id=row["owner_id"]
    )

    assert principal.kind == "flow_owner"
    assert principal.interactive is False
    assert principal.user_id == row["owner_id"]

    with pytest.raises(ConnectionNotAuthorizedError):
        await _resolve(row["name"], principal)


@pytest.mark.usefixtures("active_user")
async def test_webhook_connection_with_opt_in_resolves_the_flow_owner(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """The same webhook run resolves once the owner sets allow_non_interactive.

    The caller is deliberately a DIFFERENT user than the owner (the API-key
    webhook mode), proving the family runs as the published flow's owner rather
    than as whoever authenticated the request.
    """
    row = await _create_connection(
        client, logged_in_headers, name=f"webhook_optin_{uuid4().hex[:8]}", allow_non_interactive=True
    )
    principal = execution_principal_for(FAMILY_WEBHOOK, user=SimpleNamespace(id=uuid4()), flow_owner_id=row["owner_id"])

    assert principal.user_id == row["owner_id"]

    resolved = await _resolve(row["name"], principal)

    assert resolved.access_token.get_secret_value() == ACCESS_TOKEN


@pytest.mark.usefixtures("active_user")
async def test_a_hitl_resume_runs_as_the_job_owner_not_the_flow_owner(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """A share holder's resumed run must not borrow the flow owner's credential.

    A v2 background run can be submitted against a flow the caller only holds an
    execute share on, so ``flow.user_id`` and ``job.user_id`` genuinely differ.
    The resume keeps the STARTING JOB's owner, which is what the matrix row
    ``job_owner_reresolved`` means; reading the flow owner instead would resolve
    somebody else's opted-in connection on a worker with nobody present.
    """
    row = await _create_connection(
        client, logged_in_headers, name=f"hitl_{uuid4().hex[:8]}", allow_non_interactive=True
    )
    flow_owner_id = row["owner_id"]
    job_owner = SimpleNamespace(id=uuid4())

    borrowed = execution_principal_for(FAMILY_WORKFLOW_HITL_V2, user=job_owner, flow_owner_id=flow_owner_id)

    assert borrowed.kind == "job_owner"
    assert borrowed.user_id == str(job_owner.id)
    assert borrowed.user_id != flow_owner_id

    with pytest.raises(IntegrationError):
        await _resolve(row["name"], borrowed)

    # The owner resuming their OWN job still resolves the opted-in row.
    own = execution_principal_for(
        FAMILY_WORKFLOW_HITL_V2, user=SimpleNamespace(id=UUID(flow_owner_id)), flow_owner_id=flow_owner_id
    )
    resolved = await _resolve(row["name"], own)

    assert resolved.access_token.get_secret_value() == ACCESS_TOKEN


@pytest.mark.usefixtures("active_user")
async def test_mcp_projects_auth_none_runs_anonymously_and_non_interactively(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """An unauthenticated MCP project transport cannot borrow the owner's credential."""
    row = await _create_connection(client, logged_in_headers, name=f"mcp_{uuid4().hex[:8]}", allow_non_interactive=True)
    principal = execution_principal_for(
        FAMILY_MCP_PROJECTS,
        user=public_execution_user(),
        flow_owner_id=row["owner_id"],
        interactive=False,
    )

    assert principal.kind == "anonymous_public"
    assert principal.interactive is False

    with pytest.raises(IntegrationError):
        await _resolve(row["name"], principal)


@pytest.mark.usefixtures("active_user")
async def test_a2a_public_admission_never_resolves_a_user_connection(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """A2A's compatibility-derived public grant resolves no user connection."""
    row = await _create_connection(client, logged_in_headers, name=f"a2a_{uuid4().hex[:8]}", allow_non_interactive=True)
    principal = execution_principal_for(FAMILY_A2A, user=public_execution_user(), flow_owner_id=row["owner_id"])

    assert principal.kind == "anonymous_public"

    with pytest.raises(IntegrationError):
        await _resolve(row["name"], principal)


@pytest.mark.usefixtures("active_user")
async def test_owner_only_families_ignore_an_explicit_connection_share(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A share widens interactive_chat but never the owner-only MCP families.

    The share branch needs an authorization service that supports cross-user
    fetch and approves the grant; OSS ships a pass-through that does neither, so
    it is stubbed here. That stub is the only thing standing in for Enterprise.
    """
    row = await _create_connection(client, logged_in_headers, name=f"shared_{uuid4().hex[:8]}")
    share_holder = SimpleNamespace(id=uuid4())

    class _AuthzStub:
        async def supports_cross_user_fetch(self) -> bool:
            return True

        async def batch_enforce(self, *, user_id, domain, requests, context=None):  # noqa: ARG002
            assert context == {"execution_principal_kind": "actor"}
            return [True] * len(requests)

    monkeypatch.setattr(connection_service, "get_authorization_service", _AuthzStub)
    monkeypatch.setattr(
        connection_service,
        "get_settings_service",
        lambda: SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True)),
    )

    allowed = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=share_holder, flow_owner_id=row["owner_id"])
    assert allowed.allow_explicit_shares is True
    resolved = await _resolve(row["name"], allowed)
    assert resolved.access_token.get_secret_value() == ACCESS_TOKEN

    owner_only = execution_principal_for(FAMILY_LEGACY_MCP, user=share_holder, flow_owner_id=row["owner_id"])
    assert owner_only.allow_explicit_shares is False
    with pytest.raises(ConnectionUnresolvedError):
        await _resolve(row["name"], owner_only)
