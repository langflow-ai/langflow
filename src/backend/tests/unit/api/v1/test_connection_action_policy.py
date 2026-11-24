"""Connection consent follows the actions still available to the caller."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from lfx.extension.bundle_registry import BundleRecord, get_default_registry
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def google_policy(monkeypatch):
    path = Path(__file__).parents[5] / "bundles/google/src/lfx_google/components/google/capabilities.v1.json"
    manifest = IntegrationCapabilityManifest.model_validate_json(path.read_text())
    registry = get_default_registry()
    bundle_name = "connection_policy_google_test"
    already_loaded = any(item.provider_id == "google" for item in registry.list_integrations())
    if not already_loaded:
        registry.install_bundle(
            BundleRecord(
                bundle=bundle_name,
                extension_id="lfx-google-test",
                extension_version="1.13.0",
                slot="extra",
                integrations=(
                    LoadedIntegration(
                        extension_id="lfx-google-test",
                        extension_version="1.13.0",
                        bundle=bundle_name,
                        provider_id="google",
                        manifest_path=path,
                        capability_manifest=manifest,
                    ),
                ),
            )
        )
    monkeypatch.setenv(
        "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS",
        json.dumps(
            {
                "google-work": {
                    "provider": "google",
                    "client_id": "test-google-client",
                    "client_secret": "test-google-secret",  # pragma: allowlist secret
                    "redirect_uri": "https://langflow.example/api/v1/connections/oauth/google/callback",
                    "scopes": ["https://www.googleapis.com/auth/gmail.send"],
                }
            }
        ),
    )
    bundle = get_policy_bundle_service()
    original = bundle.snapshot

    def publish(*, block_triggers: bool):
        blocked = frozenset(
            key
            for capability in manifest.capabilities
            if block_triggers or ".trigger." not in capability.id
            for key in capability.policy_keys
        )
        bundle.publish(
            replace(
                original,
                revision=bundle.snapshot.revision + 1,
                initialized=True,
                approved_integration_provider_ids=frozenset({"google"}),
                blocked_integration_action_keys=blocked,
            )
        )
        get_integration_policy_service().invalidate()

    yield publish
    bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
    get_integration_policy_service().invalidate()
    if not already_loaded:
        registry.remove_bundle(bundle_name)


def _connection():
    return {
        "provider_key": "google",
        "name": "policy_test",
        "display_name": "Policy test",
        "executing_identity": {"identity": "user_delegated"},
    }


@pytest.mark.parametrize("block_triggers", [True, False])
@pytest.mark.parametrize("surface", ["catalog", "registrations", "create"])
async def test_action_policy_controls_discovery_registrations_and_creation(
    client,
    logged_in_headers,
    google_policy,
    block_triggers,
    surface,
):
    google_policy(block_triggers=block_triggers)
    if surface == "catalog":
        catalog = await client.get("api/v1/integrations", headers=logged_in_headers)
        assert catalog.status_code == 200
        providers = catalog.json()["providers"]
        if block_triggers:
            assert providers == []
        else:
            assert len(providers) == 1
            assert all(".trigger." in action["id"] for action in providers[0]["capabilities"])
    elif surface == "registrations":
        registrations = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)
        assert registrations.status_code == 200
        expected = [] if block_triggers else ["google-work"]
        assert [entry["id"] for entry in registrations.json()["registrations"]] == expected
    else:
        created = await client.post("api/v1/connections", json=_connection(), headers=logged_in_headers)
        assert created.status_code == (403 if block_triggers else 201), created.text
        if block_triggers:
            assert created.json()["detail"]["error_code"] == "policy-blocked"
            listed = await client.get("api/v1/connections", headers=logged_in_headers)
            assert listed.json() == []


async def test_reconnect_rechecks_action_policy(client, logged_in_headers, google_policy):
    created = await client.post("api/v1/connections", json=_connection(), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    google_policy(block_triggers=True)
    response = await client.post(
        f"api/v1/connections/{created.json()['id']}/oauth/start",
        json={"registration_id": "google-work", "scopes": ["https://www.googleapis.com/auth/gmail.send"]},
        headers=logged_in_headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error_code"] == "policy-blocked"
    assert "set-cookie" not in response.headers
