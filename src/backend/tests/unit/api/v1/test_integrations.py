"""Effective integration policy and governed provider catalog (INT-7, LE-2465)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from lfx.extension.bundle_registry import BundleRecord, get_default_registry
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

PROVIDER = "google_workspace"
# Keep the absent-provider ceiling independent of installed integration bundles.
UNLOADED_PROVIDER = "test_unloaded_provider"
SEARCH_CAPABILITY = f"{PROVIDER}.drive.files.search"
DELETE_CAPABILITY = f"{PROVIDER}.drive.files.delete"
SEARCH_KEY = f"integrations.{PROVIDER}.drive.search"
DELETE_KEY = f"integrations.{PROVIDER}.drive.delete"


def _manifest() -> IntegrationCapabilityManifest:
    return IntegrationCapabilityManifest(
        schema_version=1,
        provider_id=PROVIDER,
        display_name="Google Workspace",
        docs_url="https://example.invalid/docs",
        auth_profiles=[
            {
                "id": "user",
                "kind": "oauth2_authorization_code",
                "identity": "user_delegated",
                "default_scopes": ["drive.file"],
            }
        ],
        capabilities=[
            {
                "id": SEARCH_CAPABILITY,
                "display_name": "Drive: Search Files",
                "auth_profile_id": "user",
                "identity": "user_delegated",
                "required_scopes": ["drive.file"],
                "policy_keys": [SEARCH_KEY],
                "substrate": "sdk",
                "maturity": "ga",
                "deployment_contexts": ["hosted"],
                "risk": "read",
                "component_ref": "GoogleDriveSearchComponent",
            },
            {
                "id": DELETE_CAPABILITY,
                "display_name": "Drive: Delete File",
                "auth_profile_id": "user",
                "identity": "user_delegated",
                "required_scopes": ["drive.file"],
                "policy_keys": [DELETE_KEY],
                "substrate": "sdk",
                "maturity": "ga",
                "deployment_contexts": ["hosted"],
                "risk": "destructive",
                "component_ref": "GoogleDriveActionComponent",
            },
        ],
    )


@pytest.fixture
def loaded_integration():
    """Install one capability manifest into the process-wide bundle registry."""
    registry = get_default_registry()
    record = BundleRecord(
        bundle="google_workspace_test",
        extension_id="lfx-google-test",
        extension_version="1.13.0",
        slot="extra",
        integrations=(
            LoadedIntegration(
                extension_id="lfx-google-test",
                extension_version="1.13.0",
                bundle="google_workspace_test",
                provider_id=PROVIDER,
                manifest_path=Path("capabilities.v1.json"),
                capability_manifest=_manifest(),
            ),
        ),
    )
    registry.install_bundle(record)
    yield record
    registry.remove_bundle(record.bundle)


@pytest.fixture
def integration_policy():
    """Publish integration governance for one test and restore it afterwards."""
    bundle = get_policy_bundle_service()
    original = bundle.snapshot

    def _publish(*, providers: frozenset[str] = frozenset(), actions: frozenset[str] = frozenset()) -> None:
        bundle.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                approved_integration_provider_ids=providers,
                blocked_integration_action_keys=actions,
            )
        )
        get_integration_policy_service().invalidate()

    yield _publish

    bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
    get_integration_policy_service().invalidate()


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_list_integrations_is_unrestricted_without_a_policy(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    """QA: OSS pass-through behavior remains unchanged when no integration policy is set."""
    response = await client.get("api/v1/integrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    providers = {item["provider_id"]: item for item in response.json()["providers"]}
    assert PROVIDER in providers
    entry = providers[PROVIDER]
    assert entry["approved"] is True
    assert entry["enabled"] is False
    assert entry["connection_count"] == 0
    assert {capability["id"] for capability in entry["capabilities"]} == {SEARCH_CAPABILITY, DELETE_CAPABILITY}
    assert all(capability["allowed"] for capability in entry["capabilities"])


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_list_integrations_omits_a_provider_outside_the_ceiling(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    """QA: discovery enforces provider policy."""
    integration_policy(providers=frozenset({UNLOADED_PROVIDER}))

    response = await client.get("api/v1/integrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert [item["provider_id"] for item in response.json()["providers"]] == []


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_list_integrations_omits_a_blocked_action(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    """QA: discovery enforces action policy."""
    integration_policy(actions=frozenset({DELETE_KEY}))

    response = await client.get("api/v1/integrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    entry = next(item for item in response.json()["providers"] if item["provider_id"] == PROVIDER)
    assert [capability["id"] for capability in entry["capabilities"]] == [SEARCH_CAPABILITY]


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_include_blocked_is_refused_for_a_non_superuser(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    """A plain caller may not enumerate the operator's deny decision.

    Mirrors ``/api/v1/all``, starter projects and basic examples: the default
    listing already hides what execution would refuse, and ``include_blocked``
    is the operator panel's view of *why*.
    """
    integration_policy(providers=frozenset({UNLOADED_PROVIDER}), actions=frozenset({DELETE_KEY}))

    response = await client.get("api/v1/integrations?include_blocked=true", headers=logged_in_headers)

    assert response.status_code == 403, response.text
    # The refusal must not leak the decision it is refusing to disclose.
    assert PROVIDER not in response.text
    assert DELETE_KEY not in response.text


@pytest.mark.usefixtures("loaded_integration")
async def test_include_blocked_explains_every_decision_for_the_operator_panel(
    client: AsyncClient,
    logged_in_headers_super_user: dict[str, str],
    integration_policy,
) -> None:
    integration_policy(providers=frozenset({UNLOADED_PROVIDER}), actions=frozenset({DELETE_KEY}))

    response = await client.get("api/v1/integrations?include_blocked=true", headers=logged_in_headers_super_user)

    assert response.status_code == 200, response.text
    entry = next(item for item in response.json()["providers"] if item["provider_id"] == PROVIDER)
    assert entry["approved"] is False
    assert entry["enabled"] is False
    capabilities = {capability["id"]: capability for capability in entry["capabilities"]}
    # The provider is outside the ceiling, so every one of its actions is denied.
    assert capabilities[DELETE_CAPABILITY]["allowed"] is False
    assert capabilities[DELETE_CAPABILITY]["blocked_policy_key"] == DELETE_KEY
    assert capabilities[SEARCH_CAPABILITY]["allowed"] is False


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_provider_is_enabled_once_the_caller_has_a_connection(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    """QA: policy tests cover user enablement within the operator ceiling."""
    integration_policy(providers=frozenset({PROVIDER}))

    created = await client.post(
        "api/v1/connections",
        json={
            "provider_key": PROVIDER,
            "name": "work",
            "display_name": "Work",
            "ownership_mode": "user",
            "granted_scopes": ["drive.file"],
            "executing_identity": {"identity": "user_delegated"},
            "allow_non_interactive": False,
            "credentials": {"access_token": "token", "token_type": "Bearer"},
        },
        headers=logged_in_headers,
    )
    assert created.status_code == 201, created.text

    response = await client.get(f"api/v1/integrations?provider={PROVIDER}", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    entry = next(item for item in response.json()["providers"] if item["provider_id"] == PROVIDER)
    assert entry["enabled"] is True
    assert entry["connection_count"] == 1


@pytest.mark.usefixtures("active_user", "loaded_integration")
@pytest.mark.parametrize("visibility_mode", ["prefilter", "fallback", "revoked", "oss"])
async def test_shared_connection_counts_match_the_authorized_picker(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch, visibility_mode: str
) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from langflow.services.authorization import listing
    from langflow.services.connection import service as connection_service
    from langflow.services.database.models.connection import Connection
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_settings_service, session_scope
    from lfx.services.authorization.base import ResourceVisibilityScope

    async with session_scope() as session:
        owner = User(username=f"shared-owner-{uuid4().hex}", password="unused-hash", is_active=True)  # noqa: S106
        session.add(owner)
        await session.flush()
        rows = [
            Connection(
                owner_id=owner.id,
                provider_key=PROVIDER,
                name=name,
                display_name=name,
                executing_identity={"identity": "user_delegated"},
            )
            for name in ("shared", "unshared")
        ]
        session.add_all(rows)
        await session.flush()
        shared_id = rows[0].id
        scope = ResourceVisibilityScope(resource_ids=tuple(row.id for row in rows))

    allowed = visibility_mode in {"prefilter", "fallback"}
    authz = SimpleNamespace(
        is_enabled=AsyncMock(return_value=visibility_mode != "oss"),
        supports_cross_user_fetch=AsyncMock(return_value=True),
        get_resource_visibility=AsyncMock(return_value=None if visibility_mode == "fallback" else scope),
        batch_enforce=AsyncMock(
            side_effect=lambda **kwargs: [
                allowed and obj == f"connection:{shared_id}" for obj, _action in kwargs["requests"]
            ]
        ),
    )
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", visibility_mode != "oss")
    monkeypatch.setattr(connection_service, "get_authorization_service", lambda: authz)
    monkeypatch.setattr(listing, "get_authorization_service", lambda: authz)

    picker = await client.get(f"api/v1/connections?provider_key={PROVIDER}", headers=logged_in_headers)
    response = await client.get(f"api/v1/integrations?provider={PROVIDER}", headers=logged_in_headers)

    assert picker.status_code == response.status_code == 200
    assert [row["id"] for row in picker.json()] == ([str(shared_id)] if allowed else [])
    entry = response.json()["providers"][0]
    assert entry["connection_count"] == len(picker.json()) == int(allowed)
    assert entry["enabled"] is allowed


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_effective_policy_reports_an_unrestricted_default(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    response = await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unrestricted"] is True
    assert body["managed_externally"] is False
    assert body["blocked_action_keys"] == []
    assert PROVIDER in body["loaded_provider_ids"]
    assert PROVIDER in body["approved_provider_ids"]


@pytest.mark.usefixtures("loaded_integration")
async def test_effective_policy_reports_the_ceiling_and_deny_list(
    client: AsyncClient,
    logged_in_headers_super_user: dict[str, str],
    integration_policy,
) -> None:
    integration_policy(providers=frozenset({PROVIDER}), actions=frozenset({DELETE_KEY}))

    response = await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers_super_user)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unrestricted"] is False
    assert body["approved_provider_ids"] == [PROVIDER]
    assert body["blocked_action_keys"] == [DELETE_KEY]


@pytest.mark.usefixtures("active_user", "loaded_integration")
@pytest.mark.parametrize("approved", [True, False])
async def test_effective_policy_hides_operator_denials_from_plain_callers(
    client: AsyncClient, logged_in_headers: dict[str, str], integration_policy, *, approved: bool
) -> None:
    integration_policy(
        providers=frozenset({PROVIDER if approved else UNLOADED_PROVIDER}), actions=frozenset({DELETE_KEY})
    )

    response = await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert response.json()["blocked_action_keys"] == []
    assert response.json()["loaded_provider_ids"] == ([PROVIDER] if approved else [])
    assert DELETE_KEY not in response.text
    if not approved:
        assert PROVIDER not in response.text


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_external_empty_ceiling_is_not_reported_as_unrestricted(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch
) -> None:
    from lfx.services.integration_policy import IntegrationPolicyService

    class DenyAllPolicy(IntegrationPolicyService):
        @property
        def external_approved_integration_provider_ids(self):
            return frozenset()

        def get_allowed_provider_ids(self, **_kwargs):
            return frozenset()

    monkeypatch.setattr("lfx.services.deps.get_integration_policy_service", lambda: DenyAllPolicy())
    monkeypatch.setattr("langflow.api.v1.integrations.get_integration_policy_service", lambda: DenyAllPolicy())

    response = await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert response.json()["approved_provider_ids"] == []
    assert response.json()["unrestricted"] is False
    assert response.json()["managed_externally"] is True


async def test_integration_routes_require_authentication(client: AsyncClient) -> None:
    for path in ("api/v1/integrations", "api/v1/integrations/policy/effective"):
        response = await client.get(path)
        assert response.status_code in {401, 403}, f"{path}: {response.text}"
