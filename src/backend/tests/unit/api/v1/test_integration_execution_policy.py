"""Execution enforcement of integration policy at the host resolver (INT-7, LE-2465)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langflow.services.deps import get_connection_resolver_service
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.deps import get_policy_bundle_service
from lfx.services.policy_bundle import PolicyBundleSnapshot

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

PROVIDER = "google_workspace"


def _payload(*, name: str = "work", provider: str = PROVIDER) -> dict:
    return {
        "provider_key": provider,
        "name": name,
        "display_name": "Work Google",
        "ownership_mode": "user",
        "granted_scopes": ["calendar.readonly"],
        "executing_identity": {"identity": "user_delegated"},
        "allow_non_interactive": False,
        "credentials": {"access_token": "access-token", "token_type": "Bearer"},
    }


@pytest.fixture
def integration_policy():
    """Publish an integration ceiling / deny-list for the duration of one test."""
    bundle = get_policy_bundle_service()
    original = bundle.snapshot

    def _publish(*, providers: frozenset[str] = frozenset(), actions: frozenset[str] = frozenset()) -> None:
        from lfx.services.deps import get_integration_policy_service

        bundle.publish(
            PolicyBundleSnapshot(
                revision=original.revision + 1,
                initialized=True,
                approved_provider_ids=original.approved_provider_ids,
                blocked_component_keys=original.blocked_component_keys,
                blocked_template_keys=original.blocked_template_keys,
                blocked_model_keys=original.blocked_model_keys,
                approved_integration_provider_ids=providers,
                blocked_integration_action_keys=actions,
                content_hash=original.content_hash,
            )
        )
        get_integration_policy_service().invalidate()

    yield _publish

    from lfx.services.deps import get_integration_policy_service

    bundle.publish(
        PolicyBundleSnapshot(
            revision=original.revision + 2,
            initialized=original.initialized,
            source=original.source,
            approved_provider_ids=original.approved_provider_ids,
            blocked_component_keys=original.blocked_component_keys,
            blocked_template_keys=original.blocked_template_keys,
            blocked_model_keys=original.blocked_model_keys,
            content_hash=original.content_hash,
        )
    )
    get_integration_policy_service().invalidate()


def _principal(owner_id: str) -> ExecutionPrincipal:
    return ExecutionPrincipal(kind="actor", user_id=owner_id, actor_id=owner_id, interactive=True)


@pytest.mark.usefixtures("active_user")
async def test_resolve_denies_a_provider_outside_the_ceiling_before_reading_any_row(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    """QA: execution enforces provider policy before adapter invocation."""
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    owner_id = created.json()["owner_id"]

    integration_policy(providers=frozenset({"slack"}))

    resolver = get_connection_resolver_service()
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider=PROVIDER, name="work"),
        principal=_principal(owner_id),
    )
    with pytest.raises(IntegrationPolicyBlockedError) as excinfo:
        await resolver.resolve(request)

    assert excinfo.value.code == "policy-blocked"
    assert excinfo.value.http_status == 403


@pytest.mark.usefixtures("active_user")
async def test_resolve_succeeds_for_an_approved_provider(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    owner_id = created.json()["owner_id"]

    integration_policy(providers=frozenset({PROVIDER}))

    resolver = get_connection_resolver_service()
    resolved = await resolver.resolve(
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider=PROVIDER, name="work"),
            principal=_principal(owner_id),
        )
    )
    assert resolved.access_token.get_secret_value() == "access-token"


@pytest.mark.usefixtures("active_user")
async def test_resolve_is_unchanged_when_no_integration_policy_is_set(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """QA: OSS pass-through behavior remains unchanged when no integration policy is set."""
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    owner_id = created.json()["owner_id"]

    resolver = get_connection_resolver_service()
    resolved = await resolver.resolve(
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider=PROVIDER, name="work"),
            principal=_principal(owner_id),
        )
    )
    assert resolved.access_token.get_secret_value() == "access-token"


@pytest.mark.usefixtures("active_user")
async def test_create_connection_for_a_blocked_provider_is_403_and_stores_nothing(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    """QA: policy tests cover user enablement within the operator ceiling."""
    integration_policy(providers=frozenset({"slack"}))

    response = await client.post("api/v1/connections", json=_payload(name="blocked"), headers=logged_in_headers)

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error_code"] == "policy-blocked"

    listed = await client.get("api/v1/connections", headers=logged_in_headers)
    assert listed.status_code == 200, listed.text
    assert [item["name"] for item in listed.json()] == []


@pytest.mark.usefixtures("active_user")
async def test_create_connection_inside_the_ceiling_is_allowed(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    integration_policy(providers=frozenset({PROVIDER}))

    response = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)

    assert response.status_code == 201, response.text


@pytest.mark.usefixtures("active_user")
async def test_oauth_start_is_refused_for_a_blocked_provider(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    created = await client.post("api/v1/connections", json=_payload(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    connection_id = created.json()["id"]

    integration_policy(providers=frozenset({"slack"}))

    response = await client.post(
        f"api/v1/connections/{connection_id}/oauth/start",
        json={"registration_id": "google", "scopes": ["calendar.readonly"]},
        headers=logged_in_headers,
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error_code"] == "policy-blocked"
