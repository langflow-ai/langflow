"""Effective integration policy and governed provider catalog (INT-7, LE-2465)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from lfx.extension.bundle_registry import BundleRecord, get_default_registry
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from lfx.services.policy_bundle import PolicyBundleSnapshot

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

PROVIDER = "google_workspace"
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
            PolicyBundleSnapshot(
                revision=original.revision + 1,
                initialized=True,
                approved_integration_provider_ids=providers,
                blocked_integration_action_keys=actions,
            )
        )
        get_integration_policy_service().invalidate()

    yield _publish

    bundle.publish(PolicyBundleSnapshot(revision=original.revision + 2, initialized=original.initialized))
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
    integration_policy(providers=frozenset({"slack"}))

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
    integration_policy(providers=frozenset({"slack"}), actions=frozenset({DELETE_KEY}))

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
    integration_policy(providers=frozenset({"slack"}), actions=frozenset({DELETE_KEY}))

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


@pytest.mark.usefixtures("active_user", "loaded_integration")
async def test_effective_policy_reports_the_ceiling_and_deny_list(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    integration_policy,
) -> None:
    integration_policy(providers=frozenset({PROVIDER}), actions=frozenset({DELETE_KEY}))

    response = await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unrestricted"] is False
    assert body["approved_provider_ids"] == [PROVIDER]
    assert body["blocked_action_keys"] == [DELETE_KEY]


async def test_integration_routes_require_authentication(client: AsyncClient) -> None:
    for path in ("api/v1/integrations", "api/v1/integrations/policy/effective"):
        response = await client.get(path)
        assert response.status_code in {401, 403}, f"{path}: {response.text}"
