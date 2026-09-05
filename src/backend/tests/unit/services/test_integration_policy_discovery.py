"""Discovery enforcement for integration provider and action policy (INT-7, LE-2465)."""

from __future__ import annotations

from pathlib import Path

import pytest
from langflow.services.integration_policy_discovery import (
    IntegrationCapabilityIndex,
    build_integration_capability_index,
    candidate_provider_ids,
    component_is_allowed,
    filter_component_palette_by_integration_policy,
    graph_nodes_are_allowed,
    graph_provider_ids,
    integration_requirements,
    reset_integration_capability_index,
)
from lfx.extension.bundle_registry import BundleRecord, BundleRegistry, get_default_registry
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.services.integration_policy import (
    IntegrationPolicyContext,
    IntegrationPolicyPurpose,
    IntegrationPolicyService,
    IntegrationPolicySnapshot,
)
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot

SEARCH_CAPABILITY = "google.drive.files.search"
DELETE_CAPABILITY = "google.drive.files.delete"
SEARCH_KEY = "integrations.google.drive.search"
DELETE_KEY = "integrations.google.drive.delete"


def _manifest() -> IntegrationCapabilityManifest:
    return IntegrationCapabilityManifest(
        schema_version=1,
        provider_id="google",
        display_name="Google",
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
def index() -> IntegrationCapabilityIndex:
    integration = LoadedIntegration(
        extension_id="lfx-google",
        extension_version="1.13.0",
        bundle="google",
        provider_id="google",
        manifest_path=Path("capabilities.v1.json"),
        capability_manifest=_manifest(),
    )
    registry = BundleRegistry()
    registry.install_bundle(
        BundleRecord(
            bundle="google",
            extension_id="lfx-google",
            extension_version="1.13.0",
            slot="extra",
            integrations=(integration,),
        )
    )
    return build_integration_capability_index(registry)


@pytest.fixture(autouse=True)
def _clear_index_cache():
    reset_integration_capability_index()
    yield
    reset_integration_capability_index()


def _connection_component(*, provider: str, capabilities: list[str]) -> dict:
    return {
        "display_name": "Google Drive",
        "template": {
            "connection": {
                "type": "connection_ref",
                "provider": provider,
                "capabilities": capabilities,
            },
            "query": {"type": "str"},
        },
    }


def _stamped_component(*, provider: str, capabilities: list[str]) -> dict:
    return {
        "display_name": "Google Drive Action",
        "metadata": {
            "integration_provider_id": provider,
            "integration_capability_ids": capabilities,
        },
        "template": {"api_key": {"type": "str"}},
    }


def _unrelated_component() -> dict:
    return {"display_name": "Prompt", "template": {"prompt": {"type": "str"}}}


def _snapshot(*, allowed: set[str], candidates: set[str], blocked: set[str] = frozenset()):
    return IntegrationPolicySnapshot(
        context=IntegrationPolicyContext(),
        purpose=IntegrationPolicyPurpose.DISCOVER,
        candidate_provider_ids=frozenset(candidates),
        allowed_provider_ids=frozenset(allowed),
        blocked_action_keys=frozenset(blocked),
    )


# --------------------------------------------------------------------------- requirement extraction


def test_requirements_read_the_connection_ref_input_declaration() -> None:
    component = _connection_component(provider="google", capabilities=[SEARCH_CAPABILITY])
    assert integration_requirements(component) == [("google", (SEARCH_CAPABILITY,))]


def test_requirements_read_the_stamped_class_identity_for_api_key_components() -> None:
    component = _stamped_component(provider="google", capabilities=[DELETE_CAPABILITY])
    assert integration_requirements(component) == [("google", (DELETE_CAPABILITY,))]


def test_unrelated_components_declare_no_integration_requirement() -> None:
    assert integration_requirements(_unrelated_component()) == []
    assert integration_requirements("not a component") == []


def test_candidate_provider_ids_collects_every_declaration() -> None:
    all_types = {
        "google": {
            "Search": _connection_component(provider="google", capabilities=[SEARCH_CAPABILITY]),
            "Action": _stamped_component(provider="slack", capabilities=[]),
        },
        "prompts": {"Prompt": _unrelated_component()},
    }
    assert candidate_provider_ids(all_types) == frozenset({"google", "slack"})


# --------------------------------------------------------------------------- component decisions


def test_component_hidden_when_its_provider_is_outside_the_ceiling(index) -> None:
    """QA: discovery enforces provider policy."""
    component = _connection_component(provider="google", capabilities=[SEARCH_CAPABILITY])
    policy = _snapshot(allowed={"slack"}, candidates={"google", "slack"})
    assert not component_is_allowed(component, policy=policy, index=index)


def test_component_hidden_only_when_every_capability_is_blocked(index) -> None:
    """QA: discovery enforces action policy."""
    component = _connection_component(
        provider="google",
        capabilities=[SEARCH_CAPABILITY, DELETE_CAPABILITY],
    )
    partially_blocked = _snapshot(allowed={"google"}, candidates={"google"}, blocked={DELETE_KEY})
    assert component_is_allowed(component, policy=partially_blocked, index=index)

    fully_blocked = _snapshot(
        allowed={"google"},
        candidates={"google"},
        blocked={DELETE_KEY, SEARCH_KEY},
    )
    assert not component_is_allowed(component, policy=fully_blocked, index=index)


def test_single_capability_component_is_hidden_when_its_action_is_blocked(index) -> None:
    component = _stamped_component(provider="google", capabilities=[DELETE_CAPABILITY])
    policy = _snapshot(allowed={"google"}, candidates={"google"}, blocked={DELETE_KEY})
    assert not component_is_allowed(component, policy=policy, index=index)


def test_unknown_capability_ids_fall_back_to_the_provider_ceiling(index) -> None:
    component = _connection_component(provider="google", capabilities=["google.unknown.action"])
    allowed = _snapshot(allowed={"google"}, candidates={"google"}, blocked={SEARCH_KEY, DELETE_KEY})
    assert component_is_allowed(component, policy=allowed, index=index)
    denied = _snapshot(allowed=set(), candidates={"google"})
    assert not component_is_allowed(component, policy=denied, index=index)


def test_unrelated_components_are_never_filtered(index) -> None:
    policy = _snapshot(allowed=set(), candidates={"google"})
    assert component_is_allowed(_unrelated_component(), policy=policy, index=index)


# --------------------------------------------------------------------------- palette filter


async def _palette_with(bundle: PolicyBundleService, monkeypatch, index):
    from lfx.services import deps as lfx_deps

    service = IntegrationPolicyService(policy_bundle_service=bundle)
    monkeypatch.setattr(lfx_deps, "get_integration_policy_service", lambda: service)
    monkeypatch.setattr(
        "langflow.services.integration_policy_discovery.build_integration_capability_index",
        lambda *_args, **_kwargs: index,
    )
    all_types = {
        "google": {
            "GoogleDriveSearchComponent": _connection_component(provider="google", capabilities=[SEARCH_CAPABILITY]),
            "GoogleDriveActionComponent": _stamped_component(provider="google", capabilities=[DELETE_CAPABILITY]),
        },
        "prompts": {"Prompt": _unrelated_component()},
    }
    return await filter_component_palette_by_integration_policy(all_types, user_id="user-1")


async def test_palette_is_unchanged_when_no_integration_policy_is_set(monkeypatch, index) -> None:
    """QA: OSS pass-through behavior remains unchanged when no integration policy is set."""
    filtered = await _palette_with(PolicyBundleService(), monkeypatch, index)
    assert set(filtered["google"]) == {"GoogleDriveSearchComponent", "GoogleDriveActionComponent"}
    assert set(filtered["prompts"]) == {"Prompt"}


async def test_palette_hides_components_outside_the_provider_ceiling(monkeypatch, index) -> None:
    bundle = PolicyBundleService()
    bundle.publish(
        PolicyBundleSnapshot(
            revision=1,
            initialized=True,
            approved_integration_provider_ids=frozenset({"slack"}),
        )
    )
    filtered = await _palette_with(bundle, monkeypatch, index)
    assert filtered["google"] == {}
    assert set(filtered["prompts"]) == {"Prompt"}


async def test_palette_hides_only_the_component_whose_action_is_blocked(monkeypatch, index) -> None:
    bundle = PolicyBundleService()
    bundle.publish(
        PolicyBundleSnapshot(
            revision=1,
            initialized=True,
            blocked_integration_action_keys=frozenset({DELETE_KEY}),
        )
    )
    filtered = await _palette_with(bundle, monkeypatch, index)
    assert set(filtered["google"]) == {"GoogleDriveSearchComponent"}


async def test_palette_never_mutates_the_process_wide_registry_cache(monkeypatch, index) -> None:
    from lfx.services import deps as lfx_deps

    bundle = PolicyBundleService()
    bundle.publish(
        PolicyBundleSnapshot(revision=1, initialized=True, approved_integration_provider_ids=frozenset({"slack"}))
    )
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    monkeypatch.setattr(lfx_deps, "get_integration_policy_service", lambda: service)
    monkeypatch.setattr(
        "langflow.services.integration_policy_discovery.build_integration_capability_index",
        lambda *_args, **_kwargs: index,
    )
    all_types = {
        "google": {"Search": _connection_component(provider="google", capabilities=[SEARCH_CAPABILITY])},
    }
    filtered = await filter_component_palette_by_integration_policy(all_types, user_id="user-1")
    assert filtered["google"] == {}
    assert set(all_types["google"]) == {"Search"}


# --------------------------------------------------------------------------- saved graphs


def _graph_node(component: dict) -> dict:
    return {"id": "node-1", "data": {"type": "GoogleDriveSearchComponent", "node": component}}


def test_graph_provider_ids_and_node_filtering(index) -> None:
    nodes = [_graph_node(_connection_component(provider="google", capabilities=[SEARCH_CAPABILITY]))]
    assert graph_provider_ids(nodes) == frozenset({"google"})
    allowed = _snapshot(allowed={"google"}, candidates={"google"})
    assert graph_nodes_are_allowed(nodes, policy=allowed, index=index)
    blocked = _snapshot(allowed={"google"}, candidates={"google"}, blocked={SEARCH_KEY})
    assert not graph_nodes_are_allowed(nodes, policy=blocked, index=index)


# --------------------------------------------------------------------------- index


def test_index_maps_capabilities_by_id(index) -> None:
    assert index.provider_ids == frozenset({"google"})
    assert index.capability(SEARCH_CAPABILITY) is not None
    assert index.capability("nope") is None
    assert index.policy_keys([SEARCH_CAPABILITY, DELETE_CAPABILITY, "unknown"]) == (SEARCH_KEY, DELETE_KEY)


def test_default_index_is_cached_per_registry_snapshot() -> None:
    first = build_integration_capability_index()
    second = build_integration_capability_index()
    assert first is second
    reset_integration_capability_index()
    assert build_integration_capability_index() is not first


def test_default_index_is_rebuilt_after_an_uninstall_and_reinstall() -> None:
    """A reinstalled bundle must not be served from the previous index.

    The cache holds the snapshot it was built from, so the record it names
    stays alive and a new record can never be a false match for it -- the
    property an ``id()``-keyed fingerprint would not have.
    """
    registry = get_default_registry()
    record = BundleRecord(
        bundle="google_cache_probe",
        extension_id="lfx-google-probe",
        extension_version="1.13.0",
        slot="extra",
        integrations=(
            LoadedIntegration(
                extension_id="lfx-google-probe",
                extension_version="1.13.0",
                bundle="google_cache_probe",
                provider_id="google",
                manifest_path=Path("capabilities.v1.json"),
                capability_manifest=_manifest(),
            ),
        ),
    )
    try:
        registry.install_bundle(record)
        with_bundle = build_integration_capability_index()
        assert "google" in with_bundle.provider_ids

        registry.remove_bundle(record.bundle)
        without_bundle = build_integration_capability_index()
        assert without_bundle is not with_bundle
        assert "google" not in without_bundle.provider_ids

        # A brand-new record for the same bundle name: identity must not match
        # the one the cache still holds, so the index is rebuilt.
        registry.install_bundle(record)
        reinstalled = build_integration_capability_index()
        assert reinstalled is not without_bundle
        assert "google" in reinstalled.provider_ids
    finally:
        registry.remove_bundle(record.bundle)
        reset_integration_capability_index()
