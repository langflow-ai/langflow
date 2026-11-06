"""Consent availability when extension metadata has not entered the runtime registry."""

from __future__ import annotations

import json
import shutil
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from langflow.services.connection import policy as connection_policy
from lfx.extension.bundle_registry import BundleRegistry
from lfx.extension.discovery import discover_all_extensions
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.services.integration_policy import (
    IntegrationPolicyContext,
    IntegrationPolicyPurpose,
    IntegrationPolicySnapshot,
)


@pytest.fixture
def unloaded_google(tmp_path, monkeypatch):
    """Discover real Google metadata without loading any provider components."""
    source = Path(__file__).parents[5] / "bundles/google/src/lfx_google"
    seed_root = tmp_path / "seeds"
    extension = seed_root / "google"
    bundle = extension / "components/google"
    bundle.mkdir(parents=True)
    extension.joinpath("extension.json").write_text(source.joinpath("extension.json").read_text())
    manifest_path = bundle / "capabilities.v1.json"
    manifest_path.write_text(source.joinpath("components/google/capabilities.v1.json").read_text())
    manifest = IntegrationCapabilityManifest.model_validate_json(manifest_path.read_text())
    registry = BundleRegistry()
    monkeypatch.setattr(connection_policy, "get_default_registry", lambda: registry)
    monkeypatch.setattr(
        connection_policy,
        "discover_all_extensions",
        lambda: discover_all_extensions(distributions=[], seed_dir_env=str(seed_root)),
        raising=False,
    )
    return manifest, manifest_path, registry


def _policy(manifest, *, block_triggers=False):
    """Restrict normal Google actions while optionally denying every trigger too."""
    return IntegrationPolicySnapshot(
        context=IntegrationPolicyContext(),
        purpose=IntegrationPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"google"}),
        allowed_provider_ids=frozenset({"google"}),
        blocked_action_keys=frozenset(
            key
            for capability in manifest.capabilities
            if block_triggers or ".trigger." not in capability.id
            for key in capability.policy_keys
        ),
    )


@pytest.mark.parametrize("block_triggers", [False, True])
async def test_unloaded_provider_uses_discovered_manifest(unloaded_google, block_triggers):
    """A blocked action does not hide an allowed trigger before component loading."""
    manifest, _, registry = unloaded_google
    assert await connection_policy.provider_has_usable_action(
        "google", _policy(manifest, block_triggers=block_triggers)
    ) is (not block_triggers)
    assert registry.list_integrations() == []


@pytest.mark.parametrize("metadata", ["missing", "invalid", "wrong_provider"])
async def test_unavailable_manifest_cannot_bypass_action_restrictions(unloaded_google, metadata):
    """A missing or invalid catalog cannot establish that an action remains allowed."""
    manifest, path, _ = unloaded_google
    if metadata == "missing":
        path.unlink()
    elif metadata == "invalid":
        path.write_text("not json")
    else:
        payload = json.loads(path.read_text())
        payload["provider_id"] = "microsoft"
        path.write_text(json.dumps(payload))
    assert not await connection_policy.provider_has_usable_action("google", _policy(manifest))


async def test_conflicting_unloaded_catalogs_cannot_establish_availability(unloaded_google):
    """Two extensions claiming Google must not broaden each other's allowed actions."""
    manifest, path, _ = unloaded_google
    extension = path.parents[2]
    duplicate = extension.parent / "other-google"
    shutil.copytree(extension, duplicate)
    declaration = duplicate / "extension.json"
    payload = json.loads(declaration.read_text())
    payload["id"] = "another-google"
    declaration.write_text(json.dumps(payload))
    assert not await connection_policy.provider_has_usable_action("google", _policy(manifest))


async def test_unrestricted_registration_can_precede_installation(unloaded_google):
    """Without action restrictions, configuring a connection still permits later bundle installation."""
    manifest, path, _ = unloaded_google
    path.unlink()
    policy = replace(_policy(manifest), blocked_action_keys=frozenset())
    assert await connection_policy.provider_has_usable_action("google", policy)


async def test_unloaded_provider_discovery_runs_once_off_the_event_loop(unloaded_google, monkeypatch):
    """A registration list shares its filesystem scan without blocking other requests."""
    manifest, _, _ = unloaded_google
    discovery = connection_policy.discover_all_extensions
    event_loop_thread = threading.get_ident()
    discovery_threads = []

    def record_discovery():
        discovery_threads.append(threading.get_ident())
        return discovery()

    monkeypatch.setattr(connection_policy, "discover_all_extensions", record_discovery)
    policy = _policy(manifest)
    providers = frozenset({"google", "microsoft"})
    policy = replace(
        policy,
        candidate_provider_ids=providers,
        allowed_provider_ids=providers,
        blocked_action_keys=policy.blocked_action_keys | {"integrations.microsoft.mail.send"},
    )

    assert await connection_policy.providers_with_usable_actions(providers, policy) == frozenset({"google"})
    assert len(discovery_threads) == 1
    assert discovery_threads[0] != event_loop_thread
